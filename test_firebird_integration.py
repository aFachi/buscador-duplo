import configparser
import pytest

from firebird_client import FirebirdClient
from sqlite_repo import SqliteRepo
from sync import SyncService
from search_service import SearchService

try:
    import firebirdsql
except Exception:  # pragma: no cover
    firebirdsql = None


@pytest.mark.integration
def test_firebird_sync_and_search(tmp_path):
    if firebirdsql is None:
        pytest.skip("firebirdsql driver not available")
    db_file = tmp_path / "example.fdb"
    try:
        con = firebirdsql.create_database(dsn=f"localhost:{db_file}", user="sysdba", password="masterkey")
    except Exception:
        pytest.skip("Firebird server not available")
    cur = con.cursor()
    cur.execute("""
        CREATE TABLE PRODUTOS (
            CODIGO VARCHAR(20) PRIMARY KEY,
            DESCRICAO VARCHAR(100),
            PRECO DECIMAL(10,2)
        )
    """)
    cur.execute("INSERT INTO PRODUTOS (CODIGO, DESCRICAO, PRECO) VALUES ('BAT1','Bateria 60Ah',100.0)")
    con.commit()
    con.close()

    cfg = configparser.ConfigParser()
    cfg["FIREBIRD"] = {
        "HOST": "localhost",
        "PORT": "3050",
        "USER": "sysdba",
        "PASSWORD": "masterkey",
        "DATABASE": str(db_file),
        "CHARSET": "UTF8",
    }
    fb = FirebirdClient(cfg)
    repo = SqliteRepo(tmp_path / "cache.db")
    repo.init_schema()
    sync = SyncService(cfg, fb, repo)
    sync.sync_products_cache()
    search = SearchService(repo, fb)
    results = search.search(produto="Bateria", veiculo="", detalhe="")
    assert any(r["codigo"] == "BAT1" for r in results)
