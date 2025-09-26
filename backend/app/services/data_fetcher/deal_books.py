from typing import Any, Dict, List

from .base import BaseFetcher


class DealBooksFetcher(BaseFetcher):
    async def fetch_company(self, query: str) -> Dict[str, Any]:
        return {"name": query, "source": "deal_books"}

    async def fetch_deals(self, query: str) -> List[Dict[str, Any]]:
        return [{"deal_id": "DB-001", "company": query, "value": 1250000}]


