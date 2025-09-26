from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ...dependencies import get_db, get_current_user
from ...models.data_source import DataSource as DataSourceModel
from ...schemas.data_source import DataSource as DataSourceSchema, DataSourceCreate


router = APIRouter()


@router.get("/", response_model=List[DataSourceSchema])
def list_sources(db: Session = Depends(get_db), user=Depends(get_current_user)):
    return db.query(DataSourceModel).order_by(DataSourceModel.name.asc()).all()


@router.post("/", response_model=DataSourceSchema, status_code=status.HTTP_201_CREATED)
def create_source(payload: DataSourceCreate, db: Session = Depends(get_db), user=Depends(get_current_user)):
    exists = db.query(DataSourceModel).filter(DataSourceModel.name == payload.name).first()
    if exists:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Data source already exists")
    obj = DataSourceModel(**payload.model_dump())
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


