import sqlite3
from typing import Any, Dict, List, Optional

SCHEMA = """
PRAGMA journal_mode=WAL;
CREATE TABLE IF NOT EXISTS produtos_cache (
    codigo TEXT PRIMARY KEY,
    descricao TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_produtos_cache_desc ON produtos_cache(descricao);
CREATE INDEX IF NOT EXISTS idx_produtos_cache_codigo ON produtos_cache(codigo);

CREATE TABLE IF NOT EXISTS veiculos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    marca TEXT NOT NULL,
    modelo TEXT NOT NULL,
    ano_inicio INTEGER,
    ano_fim INTEGER,
    motor TEXT
);
CREATE INDEX IF NOT EXISTS idx_veic_compacto ON veiculos(marca, modelo, ano_inicio, ano_fim, motor);
CREATE INDEX IF NOT EXISTS idx_veic_marca ON veiculos(marca);
CREATE INDEX IF NOT EXISTS idx_veic_modelo ON veiculos(modelo);
CREATE INDEX IF NOT EXISTS idx_veic_motor ON veiculos(motor);

CREATE TABLE IF NOT EXISTS aplicacoes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    codigo_produto TEXT NOT NULL,
    veiculo_id INTEGER NOT NULL,
    FOREIGN KEY (veiculo_id) REFERENCES veiculos(id)
);
CREATE INDEX IF NOT EXISTS idx_apl_codigo ON aplicacoes(codigo_produto);
CREATE INDEX IF NOT EXISTS idx_apl_veic ON aplicacoes(veiculo_id);

CREATE TABLE IF NOT EXISTS meta (
    k TEXT PRIMARY KEY,
    v TEXT
);
"""


class SqliteRepo:
    def __init__(self, db_path: str):
        self.db_path = db_path

    def _conn(self):
        con = sqlite3.connect(self.db_path)
        con.row_factory = sqlite3.Row
        return con

    def init_schema(self):
        with self._conn() as con:
            con.executescript(SCHEMA)

    def get_meta(self, k: str) -> Optional[str]:
        with self._conn() as con:
            cur = con.execute("SELECT v FROM meta WHERE k=?", (k,))
            row = cur.fetchone()
            return row["v"] if row else None

    def set_meta(self, k: str, v: str):
        with self._conn() as con:
            con.execute(
                "INSERT INTO meta(k, v) VALUES(?, ?) ON CONFLICT(k) DO UPDATE SET v=excluded.v",
                (k, v),
            )

    def upsert_products(self, items: List[Dict[str, Any]]):
        with self._conn() as con:
            con.executemany(
                "INSERT INTO produtos_cache(codigo, descricao) VALUES(?, ?) "
                "ON CONFLICT(codigo) DO UPDATE SET descricao=excluded.descricao",
                [(i["codigo"], i["descricao"]) for i in items],
            )

    def search_products_cache(self, q: str, limit: int = 200) -> List[Dict[str, Any]]:
        if not q.strip():
            return []
        pattern = f"%{q.strip()}%"
        with self._conn() as con:
            cur = con.execute(
                "SELECT codigo, descricao FROM produtos_cache WHERE descricao LIKE ? OR codigo LIKE ? LIMIT ?",
                (pattern, pattern, int(limit)),
            )
            return [dict(row) for row in cur.fetchall()]

    def get_products_by_codes(self, codes: List[str]) -> List[Dict[str, Any]]:
        if not codes:
            return []
        placeholders = ",".join(["?"] * len(codes))
        with self._conn() as con:
            cur = con.execute(
                f"SELECT codigo, descricao FROM produtos_cache WHERE codigo IN ({placeholders})",
                codes,
            )
            return [dict(row) for row in cur.fetchall()]

    def upsert_vehicle(
        self, marca: str, modelo: str, ano_inicio: int, ano_fim: int, motor: str = ""
    ):
        with self._conn() as con:
            cur = con.execute(
                """
                SELECT id FROM veiculos WHERE marca=? AND modelo=? AND IFNULL(ano_inicio,0)=? AND IFNULL(ano_fim,0)=? AND IFNULL(motor,'')=?
            """,
                (marca, modelo, int(ano_inicio or 0), int(ano_fim or 0), motor or ""),
            )
            row = cur.fetchone()
            if row:
                return row["id"]
            cur = con.execute(
                """
                INSERT INTO veiculos(marca, modelo, ano_inicio, ano_fim, motor) VALUES(?,?,?,?,?)
            """,
                (marca, modelo, int(ano_inicio or 0), int(ano_fim or 0), motor or ""),
            )
            return cur.lastrowid

    def find_vehicle(
        self, marca: str, modelo: str, ano_inicio: int, ano_fim: int, motor: str = ""
    ) -> Optional[Dict[str, Any]]:
        with self._conn() as con:
            cur = con.execute(
                """
                SELECT * FROM veiculos WHERE marca=? AND modelo=? AND IFNULL(ano_inicio,0)=? AND IFNULL(ano_fim,0)=? AND IFNULL(motor,'')=?
            """,
                (marca, modelo, int(ano_inicio or 0), int(ano_fim or 0), motor or ""),
            )
            row = cur.fetchone()
            return dict(row) if row else None

    def add_application(self, codigo_produto: str, veiculo_id: int):
        with self._conn() as con:
            con.execute(
                "INSERT INTO aplicacoes(codigo_produto, veiculo_id) VALUES(?,?)",
                (codigo_produto, veiculo_id),
            )

    def list_vehicles(self) -> List[Dict[str, Any]]:
        with self._conn() as con:
            cur = con.execute(
                "SELECT * FROM veiculos ORDER BY marca, modelo, ano_inicio"
            )
            return [dict(row) for row in cur.fetchall()]

    def suggest_vehicles(self, veiculo_q: str) -> List[Dict[str, Any]]:
        terms = [t.strip() for t in veiculo_q.split() if t.strip()]
        if not terms:
            return []
        with self._conn() as con:
            base_sql = """
                SELECT DISTINCT marca, modelo, IFNULL(ano_inicio,0) as ano_inicio,
                       IFNULL(ano_fim,0) as ano_fim, IFNULL(motor,'') as motor
                FROM veiculos
                WHERE 1=1
            """
            params: List[str] = []
            for t in terms:
                base_sql += " AND (marca LIKE ? OR modelo LIKE ? OR CAST(IFNULL(ano_inicio,0) AS TEXT) LIKE ? OR CAST(IFNULL(ano_fim,0) AS TEXT) LIKE ? OR IFNULL(motor,'') LIKE ?)"
                like = f"%{t}%"
                params.extend([like, like, like, like, like])
            base_sql += " ORDER BY marca, modelo LIMIT 50"
            cur = con.execute(base_sql, params)
            return [dict(row) for row in cur.fetchall()]

    def search_applications(self, veiculo_q: str) -> List[Dict[str, Any]]:
        terms = [t.strip() for t in veiculo_q.split() if t.strip()]
        with self._conn() as con:
            base_sql = """
                SELECT a.codigo_produto, v.marca, v.modelo, v.ano_inicio, v.ano_fim, IFNULL(v.motor,'') as motor
                FROM aplicacoes a
                JOIN veiculos v ON v.id = a.veiculo_id
                WHERE 1=1
            """
            params = []
            for t in terms:
                base_sql += " AND (v.marca LIKE ? OR v.modelo LIKE ? OR CAST(IFNULL(v.ano_inicio,0) AS TEXT) LIKE ? OR CAST(IFNULL(v.ano_fim,0) AS TEXT) LIKE ? OR IFNULL(v.motor,'') LIKE ?)"
                like = f"%{t}%"
                params.extend([like, like, like, like, like])
            base_sql += " LIMIT 500"
            cur = con.execute(base_sql, params)
            return [dict(row) for row in cur.fetchall()]
