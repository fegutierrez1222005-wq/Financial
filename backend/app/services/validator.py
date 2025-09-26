from datetime import datetime, timedelta
from typing import Dict

from app.core.constants import FRESHNESS_DAYS_DEFAULT


def is_stale(as_of: datetime, freshness_days: int = FRESHNESS_DAYS_DEFAULT) -> bool:
    return as_of < (datetime.utcnow() - timedelta(days=freshness_days))


def validate_financial_point(point: Dict) -> Dict:
    required_keys = {"company_id", "metric", "period", "value", "currency", "source", "as_of"}
    missing = required_keys - set(point.keys())
    return {"valid": len(missing) == 0, "missing": list(missing)}


