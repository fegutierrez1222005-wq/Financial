from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ...dependencies import get_db, get_current_user
from ...models.company import Company as CompanyModel
from ...schemas.company import Company as CompanySchema, CompanyCreate, CompanyUpdate


router = APIRouter()


@router.get("/", response_model=List[CompanySchema])
def list_companies(db: Session = Depends(get_db), user=Depends(get_current_user)):
    return db.query(CompanyModel).order_by(CompanyModel.id.desc()).all()


@router.post("/", response_model=CompanySchema, status_code=status.HTTP_201_CREATED)
def create_company(payload: CompanyCreate, db: Session = Depends(get_db), user=Depends(get_current_user)):
    obj = CompanyModel(**payload.model_dump())
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


@router.get("/{company_id}", response_model=CompanySchema)
def get_company(company_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    obj = db.get(CompanyModel, company_id)
    if not obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company not found")
    return obj


@router.put("/{company_id}", response_model=CompanySchema)
def update_company(company_id: int, payload: CompanyUpdate, db: Session = Depends(get_db), user=Depends(get_current_user)):
    obj = db.get(CompanyModel, company_id)
    if not obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company not found")
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(obj, k, v)
    db.commit()
    db.refresh(obj)
    return obj


@router.delete("/{company_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_company(company_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    obj = db.get(CompanyModel, company_id)
    if not obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company not found")
    db.delete(obj)
    db.commit()
    return None


