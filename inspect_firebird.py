import configparser
import os

try:
    from dotenv import load_dotenv
except Exception:

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


from firebird_client import FirebirdClient


def main():
    base = os.path.dirname(os.path.abspath(__file__))
    load_dotenv(os.path.join(base, ".env"))
    cfg = configparser.ConfigParser()
    cfg.read(os.path.join(base, "config.ini"), encoding="utf-8")
    fb = FirebirdClient(cfg)
    print("== Conectado ao Firebird ==")
    print("Database path:", fb.database)

    # Mostra mapeamento em uso
    sig = fb._discover_product_table()
    if not sig:
        print("Não foi possível descobrir a tabela de produtos.")
        return
    table, mapping = sig
    print("Tabela em uso:", table)
    print("Mapeamento de colunas:", mapping)

    # lista primeiras colunas
    cols = fb._table_columns(table)
    print("Colunas (ordem):", cols)

    # amostra das 5 primeiras linhas
    try:
        with fb._connect() as con:
            cur = con.cursor()
            cur.execute(f"SELECT FIRST 5 * FROM {table}")
            rows = cur.fetchall()
            print("\nAmostra de linhas (5):")
            for r in rows:
                print(tuple(r))
    except Exception as e:
        print("Falha ao obter amostra:", e)


if __name__ == "__main__":
    main()
