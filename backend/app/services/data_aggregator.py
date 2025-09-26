from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _to_date(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d")


class DeterministicFinancials:
    def __init__(self, recency_offset_days: int = 0, revenue_scale: int = 10_000_000, ebitda_margin: float = 0.18, name: str = "mock"):
        self.offset = recency_offset_days
        self.revenue_scale = revenue_scale
        self.ebitda_margin = ebitda_margin
        self.name = name

    def fetch(self, company_name: str) -> Optional[Dict[str, object]]:
        if not company_name:
            return None
        h = hashlib.sha256(company_name.encode("utf-8")).hexdigest()
        seed = int(h[:8], 16)
        revenue = (seed % self.revenue_scale) + self.revenue_scale
        ebitda = int(revenue * self.ebitda_margin)
        days_ago = (seed % 700) - self.offset
        date = _now() - timedelta(days=max(0, days_ago))
        return {
            "Revenue": float(revenue),
            "EBITDA": float(ebitda),
            "Financial Timestamp": _to_date(date),
            "Source": self.name,
        }


class DataAggregator:
    def __init__(self) -> None:
        self.sources: List[DeterministicFinancials] = [
            DeterministicFinancials(30, name="PitchBook"),
            DeterministicFinancials(60, ebitda_margin=0.2, name="CapIQ"),
            DeterministicFinancials(90, ebitda_margin=0.17, name="FactSet"),
            DeterministicFinancials(120, ebitda_margin=0.16, name="Axial"),
            DeterministicFinancials(150, ebitda_margin=0.15, name="Grata"),
            DeterministicFinancials(10, ebitda_margin=0.19, name="SEC"),
            DeterministicFinancials(5, ebitda_margin=0.22, name="DealBooks"),
            DeterministicFinancials(200, ebitda_margin=0.14, name="Websites"),
        ]

    def fetch_best(self, company_name: str) -> Optional[Dict[str, object]]:
        candidates: List[Dict[str, object]] = []
        for src in self.sources:
            try:
                data = src.fetch(company_name)
                if data and data.get("Financial Timestamp"):
                    candidates.append(data)
            except Exception:
                continue
        if not candidates:
            return None
        candidates.sort(key=lambda d: d.get("Financial Timestamp", "0000-00-00"))
        return candidates[-1]


