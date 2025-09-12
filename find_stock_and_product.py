import configparser
import os
from typing import Dict, List, Optional

from firebird_client import FirebirdClient


def main():
    base = os.path.dirname(os.path.abspath(__file__))
    cfg = configparser.ConfigParser()
    cfg.read(os.path.join(base, "config.ini"), encoding="utf-8")
    fb = FirebirdClient(cfg)

    print("== Inspecionando candidatos de PRODUTO e ESTOQUE ==")
    tables = fb._list_tables()

    product_hits: List[Dict] = []
    stock_hits: List[Dict] = []

    # critérios do próprio cliente
    prod_candidates = fb._candidate_cols
    stock_candidates = fb._candidate_stock_cols

    def find(cols: List[str], cands: List[str]) -> Optional[str]:
        setcols = {c.upper(): c for c in cols}
        for c in cands:
            if c.upper() in setcols:
                return setcols[c.upper()]
        return None

    for t in tables:
        cols = fb._table_columns(t)
        up = t.upper()

        # Produto: precisa de CODIGO + DESCRICAO plausíveis
        codigo = find(cols, prod_candidates["codigo"]) or find(
            cols, ["CODIGO"]
        )  # fallback
        descricao = find(cols, prod_candidates["descricao"]) or find(
            cols, ["DESCRICAO", "PRODUTO"]
        )  # fallback
        barras = find(cols, prod_candidates["barras"]) or None
        preco = find(cols, prod_candidates["preco"]) or None
        if codigo and descricao:
            product_hits.append(
                {
                    "table": t,
                    "codigo": codigo,
                    "descricao": descricao,
                    "barras": barras,
                    "preco": preco,
                }
            )

        # Estoque: precisa de CODPRODUTO + alguma coluna de quantidade/saldo
        codprod = find(
            cols, ["CODPRODUTO", "IDPRODUTO", "CODIGO", "ID"]
        )  # várias possibilidades
        estoque = find(cols, stock_candidates) or find(
            cols, ["SALDO", "ESTOQUE", "QTDE", "QTD"]
        )
        if codprod and estoque:
            stock_hits.append({"table": t, "codproduto": codprod, "estoque": estoque})

    print("\n-- PRODUTO (candidatos) --")
    for h in product_hits:
        print(
            f"{h['table']}: codigo={h['codigo']}, descricao={h['descricao']}, barras={h['barras']}, preco={h['preco']}"
        )

    print("\n-- ESTOQUE (candidatos) --")
    for h in stock_hits:
        print(f"{h['table']}: codproduto={h['codproduto']}, estoque={h['estoque']}")

    # pequena amostra da primeira combinação plausível
    # tenta casar por nome e depois por prioridade
    def score_prod(h):
        s = 0
        if h["table"].upper().startswith("TPROD") or h["table"].upper() == "TPRODUTO":
            s += 10
        if h["table"].upper() in ("PRODUTO", "PRODUTOS"):
            s += 8
        if h["barras"]:
            s += 2
        if h["preco"]:
            s += 2
        return s

    def score_stock(h):
        s = 0
        if "ESTOQ" in h["table"].upper():
            s += 10
        if h["estoque"].upper() in ("QTDE", "SALDO", "ESTOQUE"):
            s += 2
        return s

    product_hits.sort(key=score_prod, reverse=True)
    stock_hits.sort(key=score_stock, reverse=True)

    if product_hits:
        p = product_hits[0]
        print("\nAmostra PRODUTO (top 5):", p)
        try:
            with fb._connect() as con:
                cur = con.cursor()
                cur.execute(
                    f"SELECT FIRST 5 {p['codigo']} AS CODIGO, {p['descricao']} AS DESCRICAO FROM {p['table']}"
                )
                for r in cur.fetchall():
                    print("  ", r)
        except Exception as e:
            print("  Falha amostra produto:", e)

    if stock_hits:
        s = stock_hits[0]
        print("\nAmostra ESTOQUE (top 5):", s)
        try:
            with fb._connect() as con:
                cur = con.cursor()
                cur.execute(
                    f"SELECT FIRST 5 {s['codproduto']} AS CODPRODUTO, {s['estoque']} AS ESTOQUE FROM {s['table']}"
                )
                for r in cur.fetchall():
                    print("  ", r)
        except Exception as e:
            print("  Falha amostra estoque:", e)


if __name__ == "__main__":
    main()
