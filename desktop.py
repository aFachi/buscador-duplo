import configparser
import os
from tkinter import StringVar, Tk, ttk

from firebird_client import FirebirdClient
from search_service import SearchService
from sqlite_repo import SqliteRepo
from sync import SyncService

try:
    from dotenv import load_dotenv
except Exception:
    # fallback mínimo caso python-dotenv não esteja instalado
    def load_dotenv(path=None):
        import os

        p = path or ".env"
        if not os.path.exists(p):
            return
        for line in open(p, "r", encoding="utf-8", errors="ignore"):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                continue
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "catalogo.db")
CONFIG_PATH = os.path.join(BASE_DIR, "config.ini")

# Carrega variáveis do .env (inclui FIREBIRD_DATABASE)
load_dotenv(os.path.join(BASE_DIR, ".env"))

config = configparser.ConfigParser()
if not os.path.exists(CONFIG_PATH):
    raise RuntimeError("config.ini não encontrado.")
config.read(CONFIG_PATH, encoding="utf-8")

repo = SqliteRepo(DB_PATH)
repo.init_schema()
fb = FirebirdClient(config)
sync_service = SyncService(config, fb, repo)
search_service = SearchService(repo, fb)

root = Tk()
root.title("Buscador Duplo")
try:
    root.call("tk", "scaling", 1.25)
except Exception:
    pass
style = ttk.Style()
for theme in ("vista", "xpnative", "clam"):
    try:
        style.theme_use(theme)
        break
    except Exception:
        continue

container = ttk.Frame(root, padding=8)
container.grid(row=0, column=0, sticky="nsew")
root.rowconfigure(0, weight=1)
root.columnconfigure(0, weight=1)
container.columnconfigure(0, weight=1)

produto_var = StringVar()
veiculo_var = StringVar()
detalhe_var = StringVar()

row = 0
ttk.Label(container, text="Produto").grid(row=row, column=0, sticky="w")
row += 1
produto_entry = ttk.Entry(container, textvariable=produto_var)
produto_entry.grid(row=row, column=0, sticky="ew", padx=2, pady=2)
row += 1

ttk.Label(container, text="Veículo").grid(row=row, column=0, sticky="w")
row += 1
veiculo_entry = ttk.Entry(container, textvariable=veiculo_var)
veiculo_entry.grid(row=row, column=0, sticky="ew", padx=2, pady=2)
row += 1

ttk.Label(container, text="Detalhe").grid(row=row, column=0, sticky="w")
row += 1
detalhe_entry = ttk.Entry(container, textvariable=detalhe_var)
detalhe_entry.grid(row=row, column=0, sticky="ew", padx=2, pady=2)
row += 1

search_btn = ttk.Button(container, text="Buscar")
search_btn.grid(row=row, column=0, pady=6, sticky="e")
row += 1

cols = (
    "codigo",
    "descricao",
    "preco",
    "estoque",
    "fornecedor",
    "marca",
    "grupo",
    "subgrupo",
)
tree = ttk.Treeview(
    container,
    columns=cols,
    show="headings",
    height=18,
)
headings = {
    "codigo": "Código",
    "descricao": "Descrição",
    "preco": "Preço",
    "estoque": "Estoque",
    "fornecedor": "Fornecedor",
    "marca": "Marca",
    "grupo": "Grupo",
    "subgrupo": "Subgrupo",
}
for c in cols:
    tree.heading(c, text=headings[c])
    anchor = "center" if c in ("preco", "estoque") else "w"
    width = 90 if c in ("preco", "estoque") else (160 if c == "descricao" else 110)
    tree.column(c, anchor=anchor, width=width, stretch=True)
tree.grid(row=row, column=0, sticky="nsew")
container.rowconfigure(row, weight=1)

vsb = ttk.Scrollbar(container, orient="vertical", command=tree.yview)
tree.configure(yscrollcommand=vsb.set)
vsb.grid(row=row, column=1, sticky="ns")


def populate(items):
    tree.delete(*tree.get_children())
    if not items:
        return
    for r in items:
        tree.insert(
            "",
            "end",
            values=(
                r.get("codigo", ""),
                r.get("descricao", ""),
                r.get("preco", ""),
                r.get("estoque", ""),
                r.get("fornecedor", ""),
                r.get("marca", ""),
                r.get("grupo", ""),
                r.get("subgrupo", ""),
            ),
        )


def do_search(*_):
    res = search_service.search(produto_var.get(), veiculo_var.get(), detalhe_var.get())
    items = res.get("items", []) if isinstance(res, dict) else (res or [])
    populate(items)


search_btn.configure(command=do_search)
produto_entry.bind("<KeyRelease>", do_search)
veiculo_entry.bind("<KeyRelease>", do_search)
detalhe_entry.bind("<KeyRelease>", do_search)

# carga inicial de cache e primeiro refresh (não bloqueia UI)
try:
    sync_service.sync_products_cache()
except Exception as e:
    print(f"[WARN] Sync inicial falhou: {e}")
    # segue sem cache inicial; buscas vão tentar fallback

try:
    do_search()
except Exception as e:
    print(f"[WARN] Primeira busca falhou: {e}")

root.mainloop()
