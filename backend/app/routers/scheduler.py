from fastapi import APIRouter
from ..schemas import ScanResult
from ..services.scheduler import run_daily_scan

router = APIRouter(prefix="/api/scheduler", tags=["scheduler"])


@router.post("/run", response_model=ScanResult)
async def trigger_scan():
    """
    Manually trigger the daily scan job.
    Fetches new conversations, identifies unanswered messages, and creates AI drafts.
    """
    result = await run_daily_scan()
    return ScanResult(**result)
