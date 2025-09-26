from abc import ABC, abstractmethod
from typing import Any, Dict, List

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type


class ExternalAPIError(Exception):
    pass


class BaseFetcher(ABC):
    def __init__(self, base_url: str, headers: Dict[str, str] | None = None) -> None:
        self.base_url = base_url.rstrip("/")
        self.headers = headers or {}

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=8), reraise=True,
           retry=retry_if_exception_type(ExternalAPIError))
    async def _get(self, path: str, params: Dict[str, Any] | None = None) -> Dict[str, Any]:
        url = f"{self.base_url}/{path.lstrip('/')}"
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(url, headers=self.headers, params=params)
                if resp.status_code >= 400:
                    raise ExternalAPIError(f"GET {url} failed: {resp.status_code}")
                return resp.json()
        except httpx.HTTPError as exc:
            raise ExternalAPIError(str(exc))

    @abstractmethod
    async def fetch_company(self, query: str) -> Dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    async def fetch_deals(self, query: str) -> List[Dict[str, Any]]:
        raise NotImplementedError


