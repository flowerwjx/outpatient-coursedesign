from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.middleware.auth import require_role
from app.models.user import User
from app.schemas.prescription import PrescriptionCreate, PrescriptionOut
from app.schemas.registration import RegistrationOut
from app.services import prescription_service

router = APIRouter(prefix="/api/prescriptions", tags=["prescriptions"])
workbench_router = APIRouter(prefix="/api/doctor", tags=["doctor-workbench"])


def _raise_http(exc: prescription_service.PrescriptionServiceError) -> None:
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
