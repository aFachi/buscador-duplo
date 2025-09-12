import argparse
import os
import configparser
from typing import List, Tuple

from firebird_client import FirebirdClient


def get_text_columns(fb: FirebirdClient, table: str) -> List[str]:
    sql = (
        "SELECT TRIM(rf.RDB$FIELD_NAME) "
        "FROM RDB$RELATION_FIELDS rf "
        "JOIN RDB$FIELDS f ON f.RDB$FIELD_NAME = rf.RDB$FIELD_SOURCE "
        "WHERE rf.RDB$RELATION_NAME = ? AND f.RDB$FIELD_TYPE IN (14,37,40) "
        "ORDER BY rf.RDB$FIELD_POSITION"
    )
    with fb._connect() as con:
        cur = con.cursor()
        cur.execute(sql, (table.upper(),))
        return [r[0] for r in cur.fetchall()]


def main():
    p = argparse.ArgumentParser(
        description="Busca global em colunas de texto de todas as tabelas."
    )
    p.add_argument("term", help="Termo a buscar (CONTAINING)")
    p.add_argument("--limit", type=int, default=50, help="Limite total de hits")
    args = p.parse_args()

    base = os.path.dirname(os.path.abspath(__file__))
    cfg = configparser.ConfigParser()
    cfg.read(os.path.join(base, "config.ini"), encoding="utf-8")
    fb = FirebirdClient(cfg)

    term = args.term
    remaining = args.limit
    tables = fb._list_tables()
    print(f"Procurando '{term}' em {len(tables)} tabelas...")

    for t in tables:
        if remaining <= 0:
            break
        try:
            cols = get_text_columns(fb, t)
            # foco em colunas com nome que indica descrição/produto
            preferred = [
                c for c in cols if any(k in c.upper() for k in ("PROD", "DESC", "NOME"))
            ]
            scan_cols = preferred or cols[:3]
            if not scan_cols:
                continue
            where = " OR ".join([f"{c} CONTAINING ?" for c in scan_cols])
            sql = f"SELECT FIRST {min(remaining, 10)} {', '.join(scan_cols)} FROM {t} WHERE {where}"
            with fb._connect() as con:
                cur = con.cursor()
                cur.execute(sql, tuple([term] * len(scan_cols)))
                rows = cur.fetchall()
            if rows:
                print(f"\n[{t}] {len(rows)} registro(s):")
                print(" | ".join(scan_cols))
                for r in rows:
                    print(r)
                remaining -= len(rows)
        except Exception:
            continue


if __name__ == "__main__":
    main()
