import os
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Tuple
import configparser

"""Compat: Python 3.13 removeu locale.resetlocale e o pacote fdb ainda o importa.
Definimos um shim antes de importar fdb para evitar ImportError.
"""
import locale as _locale

if not hasattr(_locale, "resetlocale"):

    def _resetlocale(category=_locale.LC_ALL):  # type: ignore
        try:
            _locale.setlocale(category, "")
        except Exception:
            pass

    _locale.resetlocale = _resetlocale  # type: ignore

try:
    import fdb as _fdb  # Firebird Python driver (requer fbclient.dll)

    _HAS_FDB = True
except Exception:
    _fdb = None
    _HAS_FDB = False
try:
    import firebirdsql as _fbsql  # Driver puro Python (conecta via wire protocol)
except Exception:
    _fbsql = None
from dotenv import load_dotenv


load_dotenv()


@dataclass
class FbConfig:
    host: str
    port: int
    database: str
    user: str
    password: str
    charset: str
    role: Optional[str] = None


def get_config() -> FbConfig:
    host = os.getenv("FIREBIRD_HOST", "127.0.0.1")
    port = int(os.getenv("FIREBIRD_PORT", "3050"))
    database = os.getenv("FIREBIRD_DATABASE", "")
    user = os.getenv("FIREBIRD_USER", "SYSDBA")
    password = os.getenv("FIREBIRD_PASSWORD", "masterkey")
    charset = os.getenv("FIREBIRD_CHARSET", "WIN1252")
    role = os.getenv("FIREBIRD_ROLE") or None
    if not database:
        raise ValueError("FIREBIRD_DATABASE não configurado no .env")
    return FbConfig(
        host=host,
        port=port,
        database=database,
        user=user,
        password=password,
        charset=charset,
        role=role,
    )


def _connect(cfg: FbConfig):
    """Conecta ao Firebird usando 'fdb' se possível; faz fallback para 'firebirdsql'.

    - 'fdb' requer fbclient.dll compatível (64 bits se Python for 64 bits).
    - 'firebirdsql' não precisa de fbclient.dll, mas requer 'passlib' para FB 2.5.
    Força charset e respeita ROLE quando disponível.
    """

    prefer = os.getenv("FB_DRIVER", "auto").lower()
    last_err: Optional[Exception] = None

    def _try_fdb():
        if not _HAS_FDB:
            return None
        try:
            return _fdb.connect(
                host=cfg.host,
                port=cfg.port,
                database=cfg.database,
                user=cfg.user,
                password=cfg.password,
                charset=cfg.charset,
                role=cfg.role,
                sql_dialect=3,
            )
        except Exception as e:  # inclui OSError WinError 193 (arquitetura inválida)
            nonlocal last_err
            last_err = e
            return None

    def _try_fbsql():
        if _fbsql is None:
            return None
        try:
            return _fbsql.connect(
                host=cfg.host,
                port=cfg.port,
                database=cfg.database,
                user=cfg.user,
                password=cfg.password,
                charset=cfg.charset,
            )
        except Exception as e:
            nonlocal last_err
            last_err = e
            return None

    conn = None
    if prefer in ("auto", "fdb"):
        conn = _try_fdb()
    if conn is None and prefer in ("auto", "firebirdsql", "fbsql"):
        conn = _try_fbsql()
    if conn is not None:
        return conn
    # nenhum funcionou
    if last_err:
        raise last_err
    raise RuntimeError(
        "Nenhum driver disponível: instale 'fdb' (com fbclient.dll) ou 'firebirdsql' + 'passlib'."
    )


@contextmanager
def fb_cursor(cfg: Optional[FbConfig] = None):
    cfg = cfg or get_config()
    conn = _connect(cfg)
    try:
        cur = conn.cursor()
        yield cur
        conn.commit()
    finally:
        try:
            cur.close()
        except Exception:
            pass
        conn.close()


def probe() -> Dict[str, Any]:
    cfg = get_config()
    info: Dict[str, Any] = {"ok": False, "steps": []}
    try:
        with fb_cursor(cfg) as cur:
            info["steps"].append("Conectado")
            cur.execute(
                "SELECT rdb$get_context('SYSTEM', 'ENGINE_VERSION') FROM RDB$DATABASE"
            )
            engine_ver = cur.fetchone()[0]
            info["engine_version"] = engine_ver

            cur.execute("SELECT FIRST 1 RDB$RELATION_NAME FROM RDB$RELATIONS")
            row = cur.fetchone()
            info["first_relation"] = (
                (row[0].strip() if isinstance(row[0], str) else row[0]) if row else None
            )

            info["ok"] = True
            return info
    except Exception as e:
        info["error"] = str(e)
        return info


# Cache local em SQLite


def get_cache_conn(path: str = "cache.db") -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS products_cache (
            key TEXT PRIMARY KEY,
            codigo TEXT,
            descricao TEXT,
            preco REAL,
            estoque REAL,
            updated_at TEXT
        )
        """
    )
    conn.commit()
    return conn


def cache_upsert(items: Iterable[Dict[str, Any]], path: str = "cache.db") -> None:
    from datetime import datetime

    conn = get_cache_conn(path)
    now = datetime.utcnow().isoformat()
    with conn:
        for it in items:
            key = str(it.get("codigo") or it.get("CODIGO") or it.get("id") or "")
            if not key:
                continue
            conn.execute(
                """
                INSERT INTO products_cache(key, codigo, descricao, preco, estoque, updated_at)
                VALUES(?, ?, ?, ?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET
                    codigo=excluded.codigo,
                    descricao=excluded.descricao,
                    preco=excluded.preco,
                    estoque=excluded.estoque,
                    updated_at=excluded.updated_at
                """,
                (
                    key,
                    it.get("codigo") or it.get("CODIGO"),
                    it.get("descricao") or it.get("DESCRICAO"),
                    it.get("preco") or it.get("PRECO"),
                    it.get("estoque") or it.get("ESTOQUE"),
                    now,
                ),
            )
    conn.close()


def default_product_query(term: str) -> Tuple[str, Tuple[Any, ...]]:
    """Constrói uma query padrão baseada na descoberta do FirebirdClient.

    Caso não seja possível descobrir a tabela/colunas, cai num SELECT genérico
    (mantido por compat), mas recomenda-se configurar SQL_PRODUCT_QUERY no .env
    ou usar overrides no config.ini (TABLE, COL_*).
    """
    is_numeric = term.isdigit()
    try:
        # Tenta reaproveitar a lógica de descoberta do FirebirdClient
        from firebird_client import FirebirdClient  # import local para evitar ciclos

        cfg = configparser.ConfigParser()
        base = os.path.dirname(os.path.abspath(__file__))
        cfg.read(os.path.join(base, "config.ini"), encoding="utf-8")
        fb = FirebirdClient(cfg)
        sig = fb._discover_product_table()
        if not sig:
            cands = fb._discover_product_candidates(max_candidates=20, lenient=True)
            if cands:
                sig = cands[0]
        if sig:
            table, mapping = sig
            codigo = mapping.get("codigo") or "CODIGO"
            descricao = mapping.get("descricao") or "DESCRICAO"
            preco = mapping.get("preco") or "CAST(NULL AS DECIMAL(18,4))"
            estoque = mapping.get("estoque") or "CAST(NULL AS DECIMAL(18,4))"

            select_cols = ", ".join(
                [
                    f"{codigo} AS CODIGO",
                    f"{descricao} AS DESCRICAO",
                    (
                        f"{preco} AS PRECO"
                        if "CAST(" in preco or " AS " in preco
                        else f"{preco} AS PRECO"
                    ),
                    (
                        f"{estoque} AS ESTOQUE"
                        if "CAST(" in estoque or " AS " in estoque
                        else f"{estoque} AS ESTOQUE"
                    ),
                ]
            )
            if is_numeric:
                where = f"CAST({codigo} AS VARCHAR(50)) = ?"
                params: Tuple[Any, ...] = (term,)
            else:
                # CONTAINING já é case-insensitive no Firebird 2.5
                where = (
                    f"{descricao} CONTAINING ? OR CAST({codigo} AS VARCHAR(50)) LIKE ?"
                )
                params = (term, f"%{term}%")
            sql = f"SELECT FIRST 50 {select_cols} FROM {table} WHERE {where} ORDER BY {descricao}"
            return sql, params
    except Exception:
        pass

    # Último recurso: consulta inócua que retorna 0 linhas (evita exception "table unknown")
    return "SELECT FIRST 0 1 FROM RDB$DATABASE", tuple()


def search_products(term: str, limit: int = 50) -> List[Dict[str, Any]]:
    # Sobreposição via env
    custom = os.getenv("SQL_PRODUCT_QUERY")
    if custom:
        sql = custom
        # simples: repetimos o termo para ? múltiplos, se necessário
        params_count = sql.count("?")
        params: Tuple[Any, ...] = tuple([term] * params_count)
    else:
        sql, params = default_product_query(term)

    # Força FIRST n se não houver e limite < 50
    if "FIRST" not in sql.upper() and limit:
        sql = sql.replace("SELECT ", f"SELECT FIRST {int(limit)} ")

    rows: List[Dict[str, Any]] = []
    with fb_cursor() as cur:
        try:
            cur.execute(sql, params)
            cols = [
                d[0].strip() if isinstance(d[0], str) else d[0] for d in cur.description
            ]
            for r in cur.fetchall():
                item = {cols[i].lower(): r[i] for i in range(len(cols))}
                rows.append(item)
            return rows
        except Exception:
            # Fallback: usa FirebirdClient para uma busca solta multi‑tabela
            try:
                from firebird_client import FirebirdClient  # local import

                cfg = configparser.ConfigParser()
                base = os.path.dirname(os.path.abspath(__file__))
                cfg.read(os.path.join(base, "config.ini"), encoding="utf-8")
                fb = FirebirdClient(cfg)
                alt = fb.search_products_loose(produto=term, limit=limit)
                return alt
            except Exception:
                return []
