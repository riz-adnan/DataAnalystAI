from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pandas as pd


DEFAULT_TTL_MINUTES = 60


class ResultStore:
    def __init__(self) -> None:
        self._store: dict[str, tuple[pd.DataFrame, datetime]] = {}

    def put(self, dataframe: pd.DataFrame, ttl_minutes: int = DEFAULT_TTL_MINUTES) -> str:
        result_id = str(uuid4())
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=ttl_minutes)
        self._store[result_id] = (dataframe.copy(), expires_at)
        return result_id

    def get(self, result_id: str) -> pd.DataFrame:
        self._cleanup()
        item = self._store.get(result_id)
        if item is None:
            raise KeyError(f"Result {result_id} was not found or has expired")
        return item[0].copy()

    def delete(self, result_id: str) -> bool:
        return self._store.pop(result_id, None) is not None

    def _cleanup(self) -> None:
        now = datetime.now(timezone.utc)
        expired_ids = [
            result_id
            for result_id, (_, expires_at) in self._store.items()
            if expires_at <= now
        ]
        for result_id in expired_ids:
            self._store.pop(result_id, None)


result_store = ResultStore()

