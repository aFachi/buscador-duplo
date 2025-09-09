import configparser
from datetime import datetime

from firebird_client import FirebirdClient
from sqlite_repo import SqliteRepo


class SyncService:
    def __init__(
        self, config: configparser.ConfigParser, fb: FirebirdClient, repo: SqliteRepo
    ):
        self.config = config
        self.fb = fb
        self.repo = repo
        self.autosync_minutes = int(config["app"].get("autosync_minutes", 0))

    def auto_sync(self):
        try:
            if self.autosync_minutes == 0:
                self.sync_products_cache()
                return
            last = self.repo.get_meta("last_sync")
            if not last:
                self.sync_products_cache()
                return
            last_dt = datetime.fromisoformat(last)
            if (datetime.now() - last_dt).total_seconds() >= self.autosync_minutes * 60:
                self.sync_products_cache()
        except Exception as e:
            print(f"[WARN] Falha no autosync: {e}")

    def sync_products_cache(self):
        items = self.fb.fetch_products_basic()
        self.repo.upsert_products(items)
        self.repo.set_meta("last_sync", datetime.now().isoformat())
