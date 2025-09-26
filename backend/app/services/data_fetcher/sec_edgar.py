from typing import Any, Dict, List

from .base import BaseFetcher


class SecEdgarFetcher(BaseFetcher):
    async def fetch_company(self, query: str) -> Dict[str, Any]:
        return {"ticker": query, "source": "sec_edgar"}

    async def fetch_deals(self, query: str) -> List[Dict[str, Any]]:
        return []


