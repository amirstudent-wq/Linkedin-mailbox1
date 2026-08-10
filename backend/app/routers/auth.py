from fastapi import APIRouter
from ..schemas import AuthStatus, SyncStatus
from ..config import settings
from ..services import linkedin as li_service

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.get("/status", response_model=AuthStatus)
async def auth_status():
    """Check whether the LinkedIn connection is working."""
    connected = li_service.is_connected()
    return AuthStatus(
        connected=connected,
        linkedin_email=settings.linkedin_email if connected else None,
        message="Connected" if connected else "Not connected. Check LINKEDIN_EMAIL and LINKEDIN_PASSWORD.",
    )
