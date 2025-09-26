from datetime import datetime
from pydantic import BaseModel, EmailStr, ConfigDict


class OutreachBase(BaseModel):
    to_email: EmailStr
    subject: str
    body: str
    status: str = "queued"


class OutreachCreate(OutreachBase):
    pass


class Outreach(OutreachBase):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


