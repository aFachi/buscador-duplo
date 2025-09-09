import configparser
import os
import threading
import time
import webbrowser

from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from jinja2 import Environment, FileSystemLoader, select_autoescape

from firebird_client import FirebirdClient
from search_service import SearchService
from sqlite_repo import SqliteRepo
from sync import SyncService

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


def _open_browser():
    time.sleep(1.5)
    try:
        webbrowser.open("http://127.0.0.1:8000")
    except:
        pass


@app.on_event("startup")
async def startup():
    sync_service.auto_sync()
    threading.Thread(target=_open_browser, daemon=True).start()


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    sync_service.auto_sync()
    template = env.get_template("index.html")
    return template.render()


@app.post("/search", response_class=HTMLResponse)
async def search(
    request: Request,
    produto: str = Form(""),
    veiculo: str = Form(""),
    detalhe: str = Form(""),
):
    sync_service.auto_sync()
    try:
        results = search_service.search(
            produto=produto, veiculo=veiculo, detalhe=detalhe
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    template = env.get_template("results.html")
    return template.render(
        produto=produto, veiculo=veiculo, detalhe=detalhe, results=results
    )


@app.get("/api/search")
async def api_search(produto: str = "", veiculo: str = "", detalhe: str = ""):
    sync_service.auto_sync()
    return JSONResponse(
        search_service.search(produto=produto, veiculo=veiculo, detalhe=detalhe)
    )


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
