from typing import Any, Dict, List

from .base import BaseFetcher


class WebScraperFetcher(BaseFetcher):
    async def fetch_company(self, query: str) -> Dict[str, Any]:
        return {"domain": query, "source": "web_scraper"}

    async def fetch_deals(self, query: str) -> List[Dict[str, Any]]:
        return []


