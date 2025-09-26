import json
from typing import Any, Optional

import redis

from app.config import get_settings


class Cache:
    def __init__(self) -> None:
        self.client = redis.from_url(get_settings().redis_url)

    def get(self, key: str) -> Optional[Any]:
        raw = self.client.get(key)
        if raw is None:
            return None
        return json.loads(raw)

    def set(self, key: str, value: Any, ttl_seconds: int = 300) -> None:
        self.client.setex(key, ttl_seconds, json.dumps(value))


