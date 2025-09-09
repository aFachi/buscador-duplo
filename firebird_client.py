from typing import List, Dict, Any
import pyfirebirdsql, configparser

class FirebirdClient:
    def __init__(self, config: configparser.ConfigParser):
        fb = config["firebird"]
        self.host = fb.get("host", "127.0.0.1")
        self.port = fb.getint("port", 3050)
        self.database_path = fb.get("database_path")
        self.user = fb.get("user")
        self.password = fb.get("password")
        self.charset = fb.get("charset", "WIN1252")
        self.sql_list_products = config["sgbr_sql"]["list_products"]
        self.sql_stock_price = config["sgbr_sql"]["stock_price_by_codes"]

    def _connect(self):
        return pyfirebirdsql.connect(
            host=self.host, port=self.port, database=self.database_path,
            user=self.user, password=self.password, charset=self.charset
        )

    def fetch_products_basic(self) -> List[Dict[str, Any]]:
        with self._connect() as con:
            cur = con.cursor()
            cur.execute(self.sql_list_products)
            rows = cur.fetchall()
            cols = [c[0].lower() for c in cur.description]
            out = []
            for r in rows:
                rec = dict(zip(cols, r))
                rec["codigo"] = str(rec["codigo"]).strip()
                rec["descricao"] = str(rec["descricao"]).strip()
                out.append(rec)
            return out

    def fetch_stock_price_by_codes(self, codes: List[str]) -> Dict[str, Dict[str, Any]]:
        if not codes: return {}
        placeholders = ",".join(["?"] * len(codes))
        sql = self.sql_stock_price.replace("{codes_in}", placeholders)
        with self._connect() as con:
            cur = con.cursor()
            cur.execute(sql, [str(c) for c in codes])
            rows = cur.fetchall()
            cols = [c[0].lower() for c in cur.description]
            result = {}
            for r in rows:
                rec = dict(zip(cols, r))
                codigo = str(rec["codigo"]).strip()
                estoque = rec.get("estoque", 0)
                preco = rec.get("preco", None)
                result[codigo] = {"estoque": estoque, "preco": float(preco) if preco is not None else None}
            return result
