from fastapi import APIRouter

from app.services.reminder_scheduler import scheduler_status


router = APIRouter(prefix="/scheduler", tags=["Scheduler"])


@router.get("/status")
def get_scheduler_status():
    return scheduler_status()