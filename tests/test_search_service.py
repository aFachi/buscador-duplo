import asyncio
import configparser

from search_service import SearchService
from sqlite_repo import SqliteRepo
from sync import SyncService


class DummyFB:
    def fetch_stock_price_by_codes(self, codes):
        return {c: {"estoque": 10.0, "preco": 100.0} for c in codes}

    def fetch_products_basic(self, limit=200):
        return [
            {"codigo": "P1", "descricao": "Bateria 60Ah"},
            {"codigo": "P2", "descricao": "Filtro de óleo"},
        ]


def test_search_and_sync(tmp_path):
    db = tmp_path / "test.db"
    repo = SqliteRepo(str(db))
    repo.init_schema()
    fb = DummyFB()
    config = configparser.ConfigParser()
    config["app"] = {"autosync_minutes": "0"}
    sync = SyncService(config, fb, repo)
    asyncio.run(sync.auto_sync())
    assert repo.get_meta("last_sync") is not None

    vid = repo.upsert_vehicle("Ford", "Fiesta", 2010, 2012, "1.6")
    repo.add_application("P1", vid)
    service = SearchService(repo, fb)
    res = service.search(produto="Bateria", veiculo="Fiesta 2011")
    assert res["count"] == 1
    item = res["items"][0]
    assert item["codigo"] == "P1"
    assert item["estoque"] == 10.0
    assert item["preco"] == 100.0
