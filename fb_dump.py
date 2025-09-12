import argparse
import configparser
import os
from typing import List

from firebird_client import FirebirdClient


def main():
    p = argparse.ArgumentParser(
        description="Dump simples: SELECT FIRST N cols FROM tabela"
    )
    p.add_argument("--table", required=True, help="Nome da tabela")
    p.add_argument(
        "--cols", default="*", help="Lista de colunas separadas por vírgula (padrão: *)"
    )
    p.add_argument(
        "--limit", type=int, default=20, help="Limite de linhas (padrão: 20)"
    )
    p.add_argument(
        "--where", default="", help="Cláusula WHERE opcional (sem a palavra WHERE)"
    )
    args = p.parse_args()

    base = os.path.dirname(os.path.abspath(__file__))
    cfg = configparser.ConfigParser()
    cfg.read(os.path.join(base, "config.ini"), encoding="utf-8")
    fb = FirebirdClient(cfg)

    table = args.table
    cols = args.cols
    limit = max(1, int(args.limit))
    where = (" WHERE " + args.where) if args.where.strip() else ""
    sql = f"SELECT FIRST {limit} {cols} FROM {table}{where}"
    print("SQL:", sql)
    with fb._connect() as con:
        cur = con.cursor()
        cur.execute(sql)
        rows = cur.fetchall()
        print(f"Linhas: {len(rows)}")
        # imprime com cabeçalho quando possível
        try:
            headers: List[str] = [d[0] for d in cur.description]
            print(" | ".join(headers))
        except Exception:
            pass
        for r in rows:
            print(r)


if __name__ == "__main__":
    main()
