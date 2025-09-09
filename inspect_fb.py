import configparser

from firebird_client import FirebirdClient


def main():
    cfg = configparser.ConfigParser()
    cfg.read("config.ini", encoding="utf-8")
    fb = FirebirdClient(cfg)

    with fb._connect() as con:
        cur = con.cursor()

        # 1) Listar tabelas de usuário
        cur.execute(
            """
            SELECT TRIM(RDB$RELATION_NAME)
            FROM RDB$RELATIONS
            WHERE COALESCE(RDB$SYSTEM_FLAG,0)=0
              AND RDB$VIEW_BLR IS NULL
            ORDER BY 1
        """
        )
        tables = [r[0] for r in cur.fetchall()]
        print("== Tabelas encontradas ==")
        for t in tables:
            print(" -", t)
        print()

        # 2) Para cada tabela, listar colunas e amostra
        for t in tables:
            cur.execute(
                """
                SELECT TRIM(rf.RDB$FIELD_NAME)
                FROM RDB$RELATION_FIELDS rf
                WHERE rf.RDB$RELATION_NAME = ?
                ORDER BY rf.RDB$FIELD_POSITION
            """,
                (t,),
            )
            cols = [r[0] for r in cur.fetchall()]
            print(f"== {t} ==")
            print("Colunas:", ", ".join(cols))
            try:
                cur.execute(f'SELECT FIRST 3 * FROM {t}')
                rows = cur.fetchall()
                for r in rows:
                    print("  ", {cols[i]: r[i] for i in range(len(cols))})
            except Exception as e:
                print("  Erro ao consultar:", e)
            print()


if __name__ == "__main__":
    main()
