# firebird_client.py
import configparser
import os
from typing import Any, Dict, List

import firebirdsql  # driver puro Python, compatível com FB 2.5


class FirebirdClient:
    def __init__(self, config: configparser.ConfigParser):
        fb = config["firebird"]
        # Permite sobrescrever via .env se você já carrega dotenv no app.py
        self.host = os.getenv("FIREBIRD_HOST", fb.get("host", "127.0.0.1"))
        self.port = int(os.getenv("FIREBIRD_PORT", fb.getint("port", 3050)))
        # No Firebird 2.5, ao conectar remotamente, "database" deve ser o CAMINHO COMPLETO no servidor.
        self.database_path = os.getenv("FIREBIRD_DB_PATH", fb.get("database_path"))
        self.user = os.getenv("FIREBIRD_USER", fb.get("user"))
        self.password = os.getenv("FIREBIRD_PASSWORD", fb.get("password"))
        self.charset = os.getenv("FIREBIRD_CHARSET", fb.get("charset", "WIN1252"))

        self.sql_list_products = config["sgbr_sql"]["list_products"]
        self.sql_stock_price = config["sgbr_sql"]["stock_price_by_codes"]

    def _connect(self):
        return firebirdsql.connect(
            host=self.host,
            port=self.port,
            database=self.database_path,  # ex.: C:/SGBR/BASESGMASTER.FDB
            user=self.user,
            password=self.password,
            charset=self.charset,
            timeout=10,
        )

    def fetch_products_basic(self) -> List[Dict[str, Any]]:
        """Retorna lista de produtos do SGBR com campos: codigo, descricao"""
        with self._connect() as con:
            cur = con.cursor()
            cur.execute(self.sql_list_products)
            rows = cur.fetchall()
            cols = [d[0].lower() for d in cur.description]
            out: List[Dict[str, Any]] = []
            for r in rows:
                rec = dict(zip(cols, r))
                rec["codigo"] = str(rec["codigo"]).strip()
                rec["descricao"] = str(rec["descricao"]).strip()
                out.append(rec)
            return out

    def fetch_stock_price_by_codes(self, codes: List[str]) -> Dict[str, Dict[str, Any]]:
        """Retorna dict: codigo -> {estoque, preco}"""
        if not codes:
            return {}
        placeholders = ",".join(["?"] * len(codes))  # firebirdsql usa paramstyle 'qmark'
        sql = self.sql_stock_price.replace("{codes_in}", placeholders)
        with self._connect() as con:
            cur = con.cursor()
            cur.execute(sql, [str(c) for c in codes])
            rows = cur.fetchall()
            cols = [d[0].lower() for d in cur.description]
            result: Dict[str, Dict[str, Any]] = {}
            for r in rows:
                rec = dict(zip(cols, r))
                codigo = str(rec["codigo"]).strip()
                estoque = rec.get("estoque", 0)
                preco = rec.get("preco", None)
                result[codigo] = {
                    "estoque": estoque,
                    "preco": float(preco) if preco is not None else None,
                }
            return result
                }
            return result
                }
            return result
