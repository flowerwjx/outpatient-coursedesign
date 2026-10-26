from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.middleware.auth import require_role
from app.models.user import User
from app.schemas.charge import ChargePreviewOut
from app.schemas.prescription import PrescriptionCreate, PrescriptionOut
from app.schemas.registration import RegistrationOut
from app.services import charge_service, prescription_service

router = APIRouter(prefix="/api/prescriptions", tags=["prescriptions"])
workbench_router = APIRouter(prefix="/api/doctor", tags=["doctor-workbench"])


def _raise_http(exc) -> None:
    raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc


@workbench_router.get(
    "/pending-registrations", response_model=list[RegistrationOut]
)
def list_my_pending_registrations(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["doctor"])),
) -> list[RegistrationOut]:
    return list(
        prescription_service.list_pending_registrations(db, current_user.id)
    )


@router.get("", response_model=list[PrescriptionOut])
def list_prescriptions(
    paid: Optional[bool] = Query(default=False),
    patient_name: Optional[str] = Query(default=None, max_length=50),
    phone: Optional[str] = Query(default=None, max_length=20),
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
    _: User = Depends(require_role(["cashier", "pharmacist"])),
) -> list[PrescriptionOut]:
    return list(
        prescription_service.list_prescriptions(
            db,
            paid=paid,
            patient_name=patient_name,
            phone=phone,
            limit=limit,
        )
    )


@router.get(
    "/{prescription_id}/charge-preview", response_model=ChargePreviewOut
)
def preview_prescription_charge(
    prescription_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_role(["cashier"])),
) -> ChargePreviewOut:
    try:
        return charge_service.preview_charge(db, prescription_id)
    except charge_service.ChargeServiceError as exc:
        _raise_http(exc)


@router.post("", response_model=PrescriptionOut, status_code=status.HTTP_201_CREATED)
def create_prescription(
    payload: PrescriptionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["doctor"])),
) -> PrescriptionOut:
    try:
        return prescription_service.create_prescription(
            db, current_user, payload
        )
    except prescription_service.PrescriptionServiceError as exc:
        _raise_http(exc)
