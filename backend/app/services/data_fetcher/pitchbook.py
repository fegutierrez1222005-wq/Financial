from typing import Any, Dict, List

from .base import BaseFetcher


class PitchBookFetcher(BaseFetcher):
    async def fetch_company(self, query: str) -> Dict[str, Any]:
        # Mocked sandbox response
        return {"name": query, "source": "pitchbook"}

    async def fetch_deals(self, query: str) -> List[Dict[str, Any]]:
        return [{"deal_id": "PB-123", "company": query, "value": 1000000}]


