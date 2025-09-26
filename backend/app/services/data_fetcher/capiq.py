from typing import Any, Dict, List

from .base import BaseFetcher


class CapiqFetcher(BaseFetcher):
    async def fetch_company(self, query: str) -> Dict[str, Any]:
        return {"name": query, "source": "capiq"}

    async def fetch_deals(self, query: str) -> List[Dict[str, Any]]:
        return [{"deal_id": "CIQ-456", "company": query, "value": 2000000}]


