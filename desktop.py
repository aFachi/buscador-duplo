import configparser
import os
from tkinter import END, Button, Entry, Label, Listbox, StringVar, Tk

from firebird_client import FirebirdClient
from search_service import SearchService
from sqlite_repo import SqliteRepo
from sync import SyncService

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "catalogo.db")
CONFIG_PATH = os.path.join(BASE_DIR, "config.ini")

config = configparser.ConfigParser()
if not os.path.exists(CONFIG_PATH):
    raise RuntimeError("config.ini não encontrado.")
config.read(CONFIG_PATH, encoding="utf-8")

repo = SqliteRepo(DB_PATH)
repo.init_schema()
fb = FirebirdClient(config)
sync_service = SyncService(config, fb, repo)
search_service = SearchService(repo, fb)

# carga inicial
sync_service.sync_products_cache()

root = Tk()
root.title("Buscador Duplo")

produto_var = StringVar()
veiculo_var = StringVar()
detalhe_var = StringVar()

Label(root, text="Produto").grid(row=0, column=0, sticky="w")
produto_entry = Entry(root, textvariable=produto_var, width=50)
produto_entry.grid(row=1, column=0, padx=5, pady=5)
produto_lb = Listbox(root, height=5, width=50)
produto_lb.grid(row=2, column=0, padx=5, sticky="we")
produto_lb.grid_remove()

Label(root, text="Veículo").grid(row=3, column=0, sticky="w")
veiculo_entry = Entry(root, textvariable=veiculo_var, width=50)
veiculo_entry.grid(row=4, column=0, padx=5, pady=5)
veiculo_lb = Listbox(root, height=5, width=50)
veiculo_lb.grid(row=5, column=0, padx=5, sticky="we")
veiculo_lb.grid_remove()

Label(root, text="Detalhe").grid(row=6, column=0, sticky="w")
detalhe_entry = Entry(root, textvariable=detalhe_var, width=50)
detalhe_entry.grid(row=7, column=0, padx=5, pady=5)

results_lb = Listbox(root, width=80, height=15)
results_lb.grid(row=9, column=0, padx=5, pady=10)


def update_produto_suggestions(*args):
    q = produto_var.get().strip()
    if len(q) < 2:
        produto_lb.grid_remove()
        return
    items = repo.search_products_cache(q, limit=10)
    produto_lb.delete(0, END)
    for item in items:
        produto_lb.insert(END, f"{item['codigo']} - {item['descricao']}")
    if items:
        produto_lb.grid()
    else:
        produto_lb.grid_remove()


def choose_produto(event):
    if not produto_lb.curselection():
        return
    produto_var.set(produto_lb.get(produto_lb.curselection()))
    produto_lb.grid_remove()


produto_entry.bind("<KeyRelease>", lambda e: update_produto_suggestions())
produto_lb.bind("<<ListboxSelect>>", choose_produto)


def update_veiculo_suggestions(*args):
    q = veiculo_var.get().strip()
    if len(q) < 2:
        veiculo_lb.grid_remove()
        return
    items = repo.suggest_vehicles(q)
    veiculo_lb.delete(0, END)
    for item in items:
        label = f"{item['marca']} {item['modelo']} {item['ano_inicio']}{'/' + str(item['ano_fim']) if item['ano_fim'] else ''} {item['motor']}".strip()
        veiculo_lb.insert(END, label)
    if items:
        veiculo_lb.grid()
    else:
        veiculo_lb.grid_remove()


def choose_veiculo(event):
    if not veiculo_lb.curselection():
        return
    veiculo_var.set(veiculo_lb.get(veiculo_lb.curselection()))
    veiculo_lb.grid_remove()


veiculo_entry.bind("<KeyRelease>", lambda e: update_veiculo_suggestions())
veiculo_lb.bind("<<ListboxSelect>>", choose_veiculo)


def do_search():
    results_lb.delete(0, END)
    res = search_service.search(produto_var.get(), veiculo_var.get(), detalhe_var.get())
    for r in res:
        price = r.get("preco", "")
        stock = r.get("estoque", "")
        results_lb.insert(END, f"{r['codigo']} - {r['descricao']} {price} {stock}")


Button(root, text="Buscar", command=do_search).grid(row=8, column=0, pady=5)

root.mainloop()
