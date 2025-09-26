from fastapi import APIRouter

from .v1 import auth, companies, data_sources, outreach, reports, webhooks, spreadsheet


api_router = APIRouter()


@api_router.get("/ping")
def ping():
    return {"message": "pong"}


api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(companies.router, prefix="/companies", tags=["companies"])
api_router.include_router(data_sources.router, prefix="/data-sources", tags=["data-sources"])
api_router.include_router(outreach.router, prefix="/outreach", tags=["outreach"])
api_router.include_router(reports.router, prefix="/reports", tags=["reports"])
api_router.include_router(webhooks.router, prefix="/webhooks", tags=["webhooks"])
api_router.include_router(spreadsheet.router, prefix="/spreadsheet", tags=["spreadsheet"])


