import configparser
import os
import threading
import time
import webbrowser
from typing import Optional

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from jinja2 import Environment, FileSystemLoader, select_autoescape
from pydantic import BaseModel, Field, validator

from firebird_client import FirebirdClient
from search_service import SearchService
from sqlite_repo import SqliteRepo
from sync import SyncService

load_dotenv()  # carrega .env para os.environ


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")
STATIC_DIR = os.path.join(BASE_DIR, "static")
DB_PATH = os.path.join(BASE_DIR, "catalogo.db")
CONFIG_PATH = os.path.join(BASE_DIR, "config.ini")

config = configparser.ConfigParser()
if not os.path.exists(CONFIG_PATH):
    raise RuntimeError("config.ini não encontrado.")
config.read(CONFIG_PATH, encoding="utf-8")

env = Environment(
    loader=FileSystemLoader(TEMPLATES_DIR),
    autoescape=select_autoescape(["html", "xml"]),
)
app = FastAPI(title="BC Auto Peças — Buscador Duplo", version="1.0.0")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

repo = SqliteRepo(DB_PATH)
repo.init_schema()
fb = FirebirdClient(config)
sync_service = SyncService(config, fb, repo)
search_service = SearchService(repo, fb)


class SearchParams(BaseModel):
    produto: str = Field("", max_length=100)
    veiculo: str = Field("", max_length=100)
    detalhe: str = Field("", max_length=100)

    @validator("produto", "veiculo", "detalhe", pre=True)
    def _strip(cls, v: Optional[str]):
        return v.strip() if isinstance(v, str) else ""


async def form_search_params(
    produto: str = Form(""), veiculo: str = Form(""), detalhe: str = Form("")
) -> SearchParams:
    return SearchParams(produto=produto, veiculo=veiculo, detalhe=detalhe)


def _open_browser():
    time.sleep(1.5)
    try:
        webbrowser.open("http://127.0.0.1:8000")
    except:
        pass


@app.on_event("startup")
async def startup():
    await sync_service.auto_sync()
    threading.Thread(target=_open_browser, daemon=True).start()


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    await sync_service.auto_sync()
    template = env.get_template("index.html")
    return template.render()


@app.post("/search", response_class=HTMLResponse)
async def search(request: Request, params: SearchParams = Depends(form_search_params)):
    await sync_service.auto_sync()
    try:
        results = search_service.search(
            produto=params.produto, veiculo=params.veiculo, detalhe=params.detalhe
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    template = env.get_template("results.html")
    return template.render(
        produto=params.produto,
        veiculo=params.veiculo,
        detalhe=params.detalhe,
        results=results,
    )


@app.get("/api/search")
async def api_search(params: SearchParams = Depends()):
    await sync_service.auto_sync()
    return JSONResponse(
        search_service.search(
            produto=params.produto, veiculo=params.veiculo, detalhe=params.detalhe
        )
    )


@app.get("/api/suggest/produto")
async def suggest_produto(q: str = ""):
    await sync_service.auto_sync()
    items = repo.search_products_cache(q, limit=20)
    return JSONResponse(items)


@app.get("/api/suggest/veiculo")
async def suggest_veiculo(q: str = ""):
    await sync_service.auto_sync()
    items = repo.suggest_vehicles(q)
    return JSONResponse(items)

@app.get("/health")
async def health():
    """Retorna estado do Firebird e timestamp da última sincronização."""
    firebird_ok = fb.ping()
    last_sync = repo.get_meta("last_sync")
    return {"firebird": firebird_ok, "last_sync": last_sync}


@app.get("/admin/aplicacoes", response_class=HTMLResponse)
async def admin_aplicacoes(request: Request):
    template = env.get_template("admin_aplicacoes.html")
    return template.render(vehicles=repo.list_vehicles())


@app.post("/admin/aplicacoes/add", response_class=HTMLResponse)
async def admin_add_aplicacao(
    request: Request,
    codigo_produto: str = Form(...),
    marca: str = Form(...),
    modelo: str = Form(...),
    ano_inicio: int = Form(...),
    ano_fim: int = Form(...),
    motor: str = Form(""),
):
    repo.upsert_vehicle(
        marca.strip(), modelo.strip(), ano_inicio, ano_fim, motor.strip()
    )
    v = repo.find_vehicle(marca, modelo, ano_inicio, ano_fim, motor)
    if not v:
        raise HTTPException(
            status_code=400, detail="Veículo não encontrado após inserir."
        )
    repo.add_application(codigo_produto.strip(), v["id"])
    return RedirectResponse(url="/admin/aplicacoes", status_code=303)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)
