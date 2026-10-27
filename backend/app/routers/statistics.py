from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.middleware.auth import require_role
from app.models.user import User
from app.schemas.statistics import DashboardOut, DailyStatisticsOut
from app.services import statistics_service

router = APIRouter(prefix="/api/statistics", tags=["statistics"])
dashboard_router = APIRouter(prefix="/api/stats", tags=["stats"])


@router.get("/today", response_model=DailyStatisticsOut)
def get_today_statistics(
    db: Session = Depends(get_db),
    _: User = Depends(require_role(["admin"])),
) -> DailyStatisticsOut:
    return statistics_service.get_daily_statistics(db)


@dashboard_router.get("/dashboard", response_model=DashboardOut)
def get_dashboard(
    db: Session = Depends(get_db),
    _: User = Depends(require_role(["admin"])),
) -> DashboardOut:
    return statistics_service.get_dashboard_statistics(db)
