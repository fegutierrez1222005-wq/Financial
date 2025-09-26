from typing import Any, Dict, List

from .base import BaseFetcher


class AxialFetcher(BaseFetcher):
    async def fetch_company(self, query: str) -> Dict[str, Any]:
        return {"name": query, "source": "axial"}

    async def fetch_deals(self, query: str) -> List[Dict[str, Any]]:
        return [{"deal_id": "AX-234", "company": query, "value": 500000}]


