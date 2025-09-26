from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ...dependencies import get_db, get_current_user

router = APIRouter()


@router.post("/{source}")
def receive_webhook(source: str, db: Session = Depends(get_db), user=Depends(get_current_user)):
    # Placeholder to log webhook receipt later
    return {"status": "received", "source": source}


