from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.middleware.auth import require_role
from app.models.user import User, UserRole
from app.schemas.user import UserOut
from app.services import user_service

router = APIRouter(prefix="/api/doctors", tags=["doctors"])


@router.get("", response_model=list[UserOut])
def list_doctors(
    db: Session = Depends(get_db),
    _: User = Depends(require_role(["admin"])),
) -> list[UserOut]:
    return list(user_service.list_by_role(db, UserRole.DOCTOR))
