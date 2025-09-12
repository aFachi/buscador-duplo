import configparser
import os

from firebird_client import FirebirdClient


def main():
    base = os.path.dirname(os.path.abspath(__file__))
    cfg = configparser.ConfigParser()
    cfg.read(os.path.join(base, "config.ini"), encoding="utf-8")
    fb = FirebirdClient(cfg)
    print("== Candidatos a tabela de produtos ==")
    tables = fb._list_tables()
    hits = []
    for t in tables:
        cols = fb._table_columns(t)
        up = t.upper()
        # filtro rápido: nomes que sugerem catálogo e não comanda/pedido/nf
        if not any(k in up for k in ("PROD", "ESTOQ")):
            continue
        if any(
            k in up
            for k in (
                "COMANDA",
                "PEDID",
                "ORCAMENT",
                "CUPOM",
                "VENDA",
                "NF",
                "NOTA",
                "MOV",
            )
        ):
            continue

        # mapeamento tentativa
        def find(cands):
            setcols = {c.upper(): c for c in cols}
            for c in cands:
                if c.upper() in setcols:
                    return setcols[c.upper()]
            return None

        mapping = {
            "codigo": find(
                ["CODPRODUTO", "CODIGO", "COD", "IDPRODUTO", "ID", "C_PRODUTO"]
            ),
            "descricao": find(
                [
                    "DESCRICAO",
                    "DESCRICAOAPLICACAO",
                    "PRODUTO",
                    "NOME",
                    "DESCR",
                    "DESCRI",
                ]
            ),
            "barras": find(["BARRAS", "CODBARRAS", "CODIGOBARRAS", "EAN", "GTIN"]),
            "preco": find(["PRECO", "PRECOVENDA", "VALOR", "PRECO1", "VLRVENDA"]),
            "estoque": find(
                [
                    "ESTOQUE",
                    "SALDO",
                    "QTDESTOQUE",
                    "QTD",
                    "QTDE",
                    "QUANTIDADE",
                    "QTD_TOTAL",
                    "QTD_DISPONIVEL",
                    "QTESTOQUE",
                ]
            ),
        }
        score = sum(1 for k in ("codigo", "descricao") if mapping.get(k))
        if score >= 2:
            hits.append((t, mapping))

    for t, m in hits:
        print(f"- {t}: {m}")


if __name__ == "__main__":
    main()
