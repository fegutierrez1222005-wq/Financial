from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

from .core.logging import setup_logging
from .config import get_settings


class LoggingMiddleware(BaseHTTPMiddleware):
    def __init__(self, app):
        super().__init__(app)
        setup_logging(get_settings().log_level)

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        return response


