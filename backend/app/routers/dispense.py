from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.middleware.auth import require_role
from app.models.user import User
from app.schemas.dispense import DispenseCreate, DispenseRecordOut
from app.services import dispense_service

router = APIRouter(prefix="/api/dispenses", tags=["dispenses"])


@router.post("", response_model=DispenseRecordOut, status_code=status.HTTP_201_CREATED)
def dispense_prescription(
    payload: DispenseCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["pharmacist"])),
) -> DispenseRecordOut:
    try:
        return dispense_service.dispense_prescription(
            db, current_user, payload
        )
    except dispense_service.DispenseServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
