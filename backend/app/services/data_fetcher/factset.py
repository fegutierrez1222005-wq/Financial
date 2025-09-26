from typing import Any, Dict, List

from .base import BaseFetcher


class FactsetFetcher(BaseFetcher):
    async def fetch_company(self, query: str) -> Dict[str, Any]:
        return {"name": query, "source": "factset"}

    async def fetch_deals(self, query: str) -> List[Dict[str, Any]]:
        return [{"deal_id": "FS-789", "company": query, "value": 3000000}]


