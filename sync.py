import asyncio
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
        # quantidade de itens para snapshot inicial do cache
        self.snapshot_limit = int(config["app"].get("snapshot_limit", 5000))
        self._task: asyncio.Task | None = None

    async def auto_sync(self):
        """Verifica necessidade de sincronização e dispara em background."""
        try:
            if self.autosync_minutes == 0:
                await self._ensure_task()
                return
            last = self.repo.get_meta("last_sync")
            if not last:
                await self._ensure_task()
                return
            last_dt = datetime.fromisoformat(last)
            if (datetime.now() - last_dt).total_seconds() >= self.autosync_minutes * 60:
                await self._ensure_task()
        except Exception as e:
            print(f"[WARN] Falha no autosync: {e}")

    async def _ensure_task(self):
        if self._task and not self._task.done():
            return
        self._task = asyncio.create_task(self.sync_products_cache_async())

    def sync_products_cache(self):
        items = self.fb.fetch_products_basic(limit=self.snapshot_limit)
        self.repo.upsert_products(items)
        self.repo.set_meta("last_sync", datetime.now().isoformat())

    async def sync_products_cache_async(self):
        await asyncio.to_thread(self.sync_products_cache)
