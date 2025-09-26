from datetime import datetime
from pydantic import BaseModel, HttpUrl, ConfigDict


class CompanyBase(BaseModel):
    name: str
    website: HttpUrl | None = None
    industry: str | None = None
    country: str | None = None


class CompanyCreate(CompanyBase):
    pass


class CompanyUpdate(CompanyBase):
    name: str | None = None
    website: HttpUrl | None = None
    industry: str | None = None
    country: str | None = None


class Company(CompanyBase):
    id: int
    last_updated_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


