from datetime import datetime
from pydantic import BaseModel, ConfigDict


class FinancialDataBase(BaseModel):
    company_id: int
    metric: str
    period: str
    value: float
    currency: str = "USD"
    source: str
    as_of: datetime


class FinancialDataCreate(FinancialDataBase):
    pass


class FinancialData(FinancialDataBase):
    id: int
    ingested_at: datetime

    model_config = ConfigDict(from_attributes=True)


