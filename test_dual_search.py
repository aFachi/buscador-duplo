from firebird_client import FirebirdClient

# consultas candidatas (ordem de preferência). Ele tenta uma por uma até preparar/executar.
CANDIDATE_QUERIES = [
    # clientes (existe no dump)
    (
        "Clientes",
        """
        SELECT FIRST 5 c.CONTROLE, c.CLIENTE
        FROM TCLIENTE c
        ORDER BY c.CONTROLE
    """,
    ),
    # contas a receber (existe no dump)
    (
        "Receber",
        """
        SELECT FIRST 5 r.CONTROLE, r.CAMINHOPDF, r.ORDENARRELATORIOSPOR
        FROM TCONFIGRECEBER r
        ORDER BY r.CONTROLE
    """,
    ),
    # SAT (existe no dump)
    (
        "SAT",
        """
        SELECT FIRST 5 s.CONTROLE, s.AMBIENTEDEDESTINO, s.NOMEDADLL
        FROM TCONFIGSAT s
        ORDER BY s.CONTROLE
    """,
    ),
    # lista os nomes das tabelas de usuário, como fallback final
    (
        "Tabelas (fallback)",
        """
        SELECT FIRST 10 TRIM(RDB$RELATION_NAME) AS TABELA
        FROM RDB$RELATIONS
        WHERE RDB$SYSTEM_FLAG = 0
        ORDER BY RDB$RELATION_NAME
    """,
    ),
]


def main():
    fb = FirebirdClient()
    print("== Smoke test (tentando uma consulta que exista) ==")
    ok = False
    with fb._connect() as con:
        cur = con.cursor()
        for label, sql in CANDIDATE_QUERIES:
            try:
                cur.execute(sql)
                rows = cur.fetchall()
                print(f"[OK] {label}: {len(rows)} registro(s)")
                for r in rows:
                    print("   ", r)
                ok = True
                break
            except Exception as e:
                print(f"[Skip] {label}: {e}")

    if not ok:
        print(
            "Nenhuma consulta candidata funcionou. Precisamos mapear as tabelas/colunas de produtos nesta base."
        )


if __name__ == "__main__":
    main()
