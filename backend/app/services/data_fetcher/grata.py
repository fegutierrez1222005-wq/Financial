from typing import Any, Dict, List

from .base import BaseFetcher


class GrataFetcher(BaseFetcher):
    async def fetch_company(self, query: str) -> Dict[str, Any]:
        return {"name": query, "source": "grata"}

    async def fetch_deals(self, query: str) -> List[Dict[str, Any]]:
        return [{"deal_id": "GR-345", "company": query, "value": 750000}]


