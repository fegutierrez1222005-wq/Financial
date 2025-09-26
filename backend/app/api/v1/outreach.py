from typing import List

from fastapi import APIRouter, Depends
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from ...dependencies import get_db, get_current_user
from ...services.outreach_manager import OutreachManager
from ...models.outreach import Outreach as OutreachModel
from ...schemas.outreach import Outreach as OutreachSchema


router = APIRouter()


class OutreachRequest(BaseModel):
    to: EmailStr
    subject: str
    body: str


@router.post("/", response_model=OutreachSchema)
def send_outreach(payload: OutreachRequest, db: Session = Depends(get_db), user=Depends(get_current_user)):
    manager = OutreachManager(db)
    record = manager.queue_email(payload.to, payload.subject, payload.body)
    return record


@router.get("/", response_model=List[OutreachSchema])
def list_outreach(db: Session = Depends(get_db), user=Depends(get_current_user)):
    return db.query(OutreachModel).order_by(OutreachModel.id.desc()).all()


