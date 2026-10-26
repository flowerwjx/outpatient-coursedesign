from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.middleware.auth import get_current_user
from app.models.user import User
from app.schemas.registration import RegistrationCreate, RegistrationOut
from app.services import registration_service

router = APIRouter(prefix="/api/registrations", tags=["registrations"])


@router.get("", response_model=list[RegistrationOut])
def list_registrations(
    schedule_date: Optional[date] = Query(default=None, alias="date"),
    schedule_id: Optional[int] = Query(default=None, gt=0),
    phone: Optional[str] = Query(default=None, max_length=20),
    patient_name: Optional[str] = Query(default=None, max_length=50),
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> list[RegistrationOut]:
    return list(
        registration_service.list_registrations(
            db,
            schedule_date=schedule_date,
            schedule_id=schedule_id,
            phone=phone,
            patient_name=patient_name,
            limit=limit,
        )
    )


@router.post("", response_model=RegistrationOut, status_code=status.HTTP_201_CREATED)
def create_registration(
    payload: RegistrationCreate,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> RegistrationOut:
    try:
        return registration_service.create_registration(db, payload)
    except registration_service.RegistrationServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
