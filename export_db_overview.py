import configparser
import os
from typing import Any, List, Tuple

try:
    from dotenv import load_dotenv
except Exception:

    def load_dotenv(path=None):
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

TYPE_NAMES = {
    7: "SMALLINT",
    8: "INTEGER",
    10: "FLOAT",
    12: "DATE",
    13: "TIME",
    14: "CHAR",
    16: "INT128",
    27: "DOUBLE",
    35: "TIMESTAMP",
    37: "VARCHAR",
    40: "CSTRING",
    261: "BLOB",
}


def type_to_str(
    ftype: int, subtype: int, length: int, precision: int, scale: int
) -> str:
    name = TYPE_NAMES.get(ftype, str(ftype))
    if ftype in (14, 37, 40):  # CHAR/VARCHAR/CSTRING
        return f"{name}({length})"
    if ftype == 16:  # INT128 or NUMERIC/DECIMAL
        # subtype 1 = NUMERIC, 2 = DECIMAL (em geral)
        if subtype == 1:
            return f"NUMERIC({precision},{abs(scale)})"
        if subtype == 2:
            return f"DECIMAL({precision},{abs(scale)})"
        return "BIGINT"
    if ftype == 261:
        return f"BLOB(sub={subtype})"
    return name


def sanitize(v: Any, maxlen: int = 120) -> str:
    if v is None:
        return ""
    try:
        if isinstance(v, (bytes, bytearray, memoryview)):
            return f"<BLOB {len(v)} bytes>"
        s = str(v)
    except Exception:
        return "<unrepr>"
    s = s.replace("\n", "\\n").replace("\r", "\\r")
    if len(s) > maxlen:
        s = s[: maxlen - 1] + "…"
    return s


def main():
    base = os.path.dirname(os.path.abspath(__file__))
    load_dotenv(os.path.join(base, ".env"))
    cfg = configparser.ConfigParser()
    cfg.read(os.path.join(base, "config.ini"), encoding="utf-8")
    fb = FirebirdClient(cfg)

    out_path = os.path.join(base, "db_overview.md")
    con = fb._connect()
    try:
        with open(out_path, "w", encoding="utf-8") as f:
            cur = con.cursor()
            cur.execute(
                "SELECT rdb$get_context('SYSTEM','ENGINE_VERSION') FROM RDB$DATABASE"
            )
            engine = cur.fetchone()[0]
            f.write(f"# Firebird Database Overview\n\n")
            f.write(f"- Database: `{fb.database}`\n")
            f.write(f"- Engine: `{engine}`\n\n")

            # lista tabelas de usuário
            cur.execute(
                """
                SELECT TRIM(RDB$RELATION_NAME)
                FROM RDB$RELATIONS
                WHERE RDB$VIEW_BLR IS NULL
                  AND (RDB$SYSTEM_FLAG IS NULL OR RDB$SYSTEM_FLAG = 0)
                ORDER BY 1
                """
            )
            tables = [r[0] for r in cur.fetchall()]

            for t in tables:
                f.write(f"## {t}\n")
                # colunas com tipo
                try:
                    cur.execute(
                        """
                        SELECT TRIM(rf.RDB$FIELD_NAME) AS COL,
                               f.RDB$FIELD_TYPE,
                               COALESCE(f.RDB$FIELD_SUB_TYPE, 0),
                               COALESCE(f.RDB$FIELD_LENGTH, 0),
                               COALESCE(f.RDB$FIELD_PRECISION, 0),
                               COALESCE(f.RDB$FIELD_SCALE, 0),
                               COALESCE(rf.RDB$NULL_FLAG, 0)
                        FROM RDB$RELATION_FIELDS rf
                        JOIN RDB$FIELDS f ON f.RDB$FIELD_NAME = rf.RDB$FIELD_SOURCE
                        WHERE rf.RDB$RELATION_NAME = ?
                        ORDER BY rf.RDB$FIELD_POSITION
                        """,
                        (t,),
                    )
                    cols_raw: List[Tuple] = cur.fetchall()
                except Exception as e:
                    f.write(f"(Falha ao ler metadados: {e})\n\n")
                    continue

                cols = []
                for name, ftype, subtype, length, prec, scale, nullflag in cols_raw:
                    cols.append(
                        (
                            name,
                            type_to_str(
                                int(ftype or 0),
                                int(subtype or 0),
                                int(length or 0),
                                int(prec or 0),
                                int(scale or 0),
                            ),
                            "NOT NULL" if int(nullflag or 0) == 1 else "NULL",
                            int(ftype or 0),
                        )
                    )
                # imprime lista de colunas
                for name, tstr, nullinfo, _ft in cols:
                    f.write(f"- `{name}`: {tstr} {nullinfo}\n")

                # amostra de dados (até 5 linhas), ignorando BLOBs no SELECT
                sample_cols = [c for c in cols if c[3] != 261]
                colnames = [c[0] for c in sample_cols]
                if not colnames:
                    f.write("\n(sem colunas selecionáveis para amostra)\n\n")
                    continue
                select_cols = ", ".join(colnames)
                try:
                    cur.execute(f"SELECT FIRST 5 {select_cols} FROM {t}")
                    rows = cur.fetchall()
                    if rows:
                        f.write("\n| " + " | ".join(colnames) + " |\n")
                        f.write("|" + "|".join([" --- "] * len(colnames)) + "|\n")
                        for r in rows:
                            f.write("| " + " | ".join(sanitize(v) for v in r) + " |\n")
                    else:
                        f.write("\n(nenhum registro)\n")
                except Exception as e:
                    f.write(f"\nFalha ao ler amostra: {e}\n")
                f.write("\n\n")
    finally:
        try:
            con.close()
        except Exception:
            pass

    print(f"Arquivo gerado: {out_path}")


if __name__ == "__main__":
    main()
