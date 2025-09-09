# probe_products.py
from __future__ import annotations

import re
from typing import Dict, List, Tuple

from firebird_client import FirebirdClient

# Palavras-chave que interessam
KEYS = [
    "PROD",
    "PRODUT",
    "PRODUTO",
    "ESTOQ",
    "ESTOQUE",
    "PRECO",
    "VALOR",
    "APLIC",
    "VEIC",
    "VEICULO",
    "GRADE",
    "NCM",
    "REFER",
    "REF",
    "DESCR",
]

# Tabelas para priorizar nome
PRIORITY_TABLE_RE = re.compile(r"(TPROD|PROD|ESTOQ|PRECO|GRADE|APLIC|VEIC)", re.I)

# Colunas para priorizar score
PRIORITY_COL_RE = re.compile(
    r"(DESCR|DESCRICAO|PRODUTO|REFER|REFERENCIA|BARRAS|ESTOQ|PRECO|VALOR|GRADE)", re.I
)


def score_table(table: str, cols: List[str]) -> int:
    s = 0
    if PRIORITY_TABLE_RE.search(table):
        s += 5
    s += sum(1 for c in cols if PRIORITY_COL_RE.search(c))
    return s


def fetch_all_user_tables(fb: FirebirdClient) -> List[str]:
    sql = """
    SELECT TRIM(r.RDB$RELATION_NAME)
    FROM RDB$RELATIONS r
    WHERE r.RDB$SYSTEM_FLAG = 0
      AND (r.RDB$VIEW_SOURCE IS NULL)
    ORDER BY 1
    """
    with fb._connect() as con:
        cur = con.cursor()
        cur.execute(sql)
        return [row[0] for row in cur.fetchall()]


def fetch_cols(fb: FirebirdClient, table: str) -> List[str]:
    sql = """
    SELECT TRIM(rf.RDB$FIELD_NAME)
    FROM RDB$RELATION_FIELDS rf
    JOIN RDB$FIELDS f ON rf.RDB$FIELD_SOURCE = f.RDB$FIELD_NAME
    WHERE rf.RDB$RELATION_NAME = ?
    ORDER BY rf.RDB$FIELD_POSITION
    """
    with fb._connect() as con:
        cur = con.cursor()
        cur.execute(sql, (table,))
        return [row[0] for row in cur.fetchall()]


def looks_interesting(table: str, cols: List[str]) -> bool:
    if PRIORITY_TABLE_RE.search(table):
        return True
    for c in cols:
        for k in KEYS:
            if k in c.upper():
                return True
    return False


def try_sample(
    fb: FirebirdClient, table: str, cols: List[str]
) -> Tuple[int, List[tuple]]:
    """
    Retorna (qtd_amostra, linhas). Tenta FIRST 5.
    """
    sql = f'SELECT FIRST 5 {", ".join(cols[:6])} FROM {table}'
    with fb._connect() as con:
        cur = con.cursor()
        try:
            cur.execute(sql)
            rows = cur.fetchall()
            return (len(rows), rows)
        except Exception as e:
            return (-1, [("erro", str(e))])


def main():
    fb = FirebirdClient()

    print("== PROBE: vasculhando tabelas de usuário ==\n")
    tables = fetch_all_user_tables(fb)
    report: List[Tuple[int, str, List[str]]] = []

    # Coletar infos e pontuar
    for t in tables:
        cols = fetch_cols(fb, t)
        if looks_interesting(t, cols):
            report.append((score_table(t, cols), t, cols))

    # Ordenar por score desc
    report.sort(key=lambda x: x[0], reverse=True)

    top = report[:30]  # mostrar top 30
    for score, t, cols in top:
        print(f"[{score:02d}] {t}")
        print("    Colunas-chave (até 10):", ", ".join(cols[:10]))
        cnt, sample = try_sample(fb, t, cols)
        if cnt >= 0:
            print(f"    Amostra: {cnt} linha(s)")
            for r in sample[:3]:
                print("       ", r)
        else:
            print("    Amostra: erro")
            print("       ", sample[0])
        print()

    # Dica de colunas candidatas de nome/descrição/referência/barras
    print("== Dicas de colunas que parecem nome/descrição/referência ==")
    for _, t, cols in top:
        namey = [
            c for c in cols if re.search(r"(DESCR|PRODUTO|NOME|REFER|BARRAS)", c, re.I)
        ]
        if namey:
            print(f"  {t}: {', '.join(namey[:6])}")


if __name__ == "__main__":
    main()
