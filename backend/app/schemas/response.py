from typing import Generic, List, Optional, TypeVar

from pydantic import BaseModel


T = TypeVar("T")


class MessageResponse(BaseModel):
    message: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class PageMeta(BaseModel):
    page: int
    size: int
    total: int


class PaginatedResponse(BaseModel, Generic[T]):
    data: List[T]
    meta: PageMeta


