from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.api.router import api_router
from app.middleware import LoggingMiddleware


def create_app() -> FastAPI:
    settings = get_settings()

    application = FastAPI(
        title="Financial Data Management System",
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )

    # CORS: open for all origins (no credentials) to support LAN dev hosts like 192.168.x.x:5173
    application.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Routers
    application.include_router(api_router, prefix=settings.api_v1_prefix)

    # Middleware
    application.add_middleware(LoggingMiddleware)

    @application.get("/health")
    def health_check():
        return {"status": "ok"}

    return application


app = create_app()


