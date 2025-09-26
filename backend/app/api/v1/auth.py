from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr

from ...config import get_settings
from ...core.security import create_access_token
from ...schemas.response import TokenResponse


router = APIRouter()


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, settings=Depends(get_settings)):
    if payload.email != settings.admin_email or payload.password != settings.admin_password:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    token = create_access_token(subject=str(payload.email), secret_key=settings.secret_key, expires_minutes=settings.access_token_expire_minutes)
    return TokenResponse(access_token=token)


