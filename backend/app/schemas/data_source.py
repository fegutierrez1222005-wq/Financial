from datetime import datetime
from pydantic import BaseModel, HttpUrl, ConfigDict


class DataSourceBase(BaseModel):
    name: str
    base_url: HttpUrl | None = None
    enabled: bool = True


class DataSourceCreate(DataSourceBase):
    pass


class DataSource(DataSourceBase):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


