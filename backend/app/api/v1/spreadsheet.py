from fastapi import APIRouter, Depends

from ...dependencies import get_current_user
from ...services.spreadsheet.workflow import run_update_and_outreach


router = APIRouter()


@router.post("/run")
def run_once(user=Depends(get_current_user)):
    return run_update_and_outreach()


