from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ...dependencies import get_db, get_current_user
from ...services.analytics import summary as build_summary

router = APIRouter()


@router.get("/summary")
def summary(db: Session = Depends(get_db), user=Depends(get_current_user)):
    return build_summary(db)


