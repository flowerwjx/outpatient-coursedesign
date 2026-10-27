from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.middleware.auth import get_current_user, require_role
from app.models.user import User
from app.schemas.schedule import ScheduleCreate, ScheduleOut, ScheduleUpdate
from app.services import schedule_service

router = APIRouter(prefix="/api/schedules", tags=["schedules"])


def _raise_http(exc: schedule_service.ScheduleServiceError) -> None:
    raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc


@router.post("", response_model=ScheduleOut, status_code=status.HTTP_201_CREATED)
def create_schedule(
    payload: ScheduleCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_role(["admin"])),
) -> ScheduleOut:
    try:
        return schedule_service.create_schedule(db, payload)
    except schedule_service.ScheduleServiceError as exc:
        _raise_http(exc)


@router.get("", response_model=list[ScheduleOut])
def list_schedules(
    schedule_date: Optional[date] = Query(default=None, alias="date"),
    department: Optional[str] = Query(default=None, max_length=100),
    doctor_id: Optional[int] = Query(default=None, gt=0),
    db: Session = Depends(get_db),
    _: User = Depends(require_role(["admin"])),
) -> list[ScheduleOut]:
    return list(
        schedule_service.list_schedules(
            db,
            schedule_date=schedule_date,
            department=department,
            doctor_id=doctor_id,
        )
    )


@router.get("/available", response_model=list[ScheduleOut])
def list_available_schedules(
    schedule_date: date = Query(..., alias="date"),
    department: Optional[str] = Query(default=None, max_length=100),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> list[ScheduleOut]:
    return list(
        schedule_service.list_available_schedules(
            db, schedule_date=schedule_date, department=department
        )
    )


@router.put("/{schedule_id}", response_model=ScheduleOut)
def update_schedule(
    schedule_id: int,
    payload: ScheduleUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_role(["admin"])),
) -> ScheduleOut:
    try:
        return schedule_service.update_schedule(db, schedule_id, payload)
    except schedule_service.ScheduleServiceError as exc:
        _raise_http(exc)


@router.delete("/{schedule_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_schedule(
    schedule_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_role(["admin"])),
) -> Response:
    try:
        schedule_service.delete_schedule(db, schedule_id)
    except schedule_service.ScheduleServiceError as exc:
        _raise_http(exc)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
