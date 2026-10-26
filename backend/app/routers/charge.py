from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.middleware.auth import require_role
from app.models.user import User
from app.schemas.charge import ChargeCreate, ChargeOrderOut
from app.services import charge_service

router = APIRouter(prefix="/api/charge-orders", tags=["charge-orders"])


@router.get("", response_model=list[ChargeOrderOut])
def list_charge_orders(
    charged_date: Optional[date] = Query(default=None, alias="date"),
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
    _: User = Depends(require_role(["cashier"])),
) -> list[ChargeOrderOut]:
    return list(
        charge_service.list_charge_orders(
            db, charged_date=charged_date, limit=limit
        )
    )


@router.post("", response_model=ChargeOrderOut, status_code=status.HTTP_201_CREATED)
def create_charge_order(
    payload: ChargeCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["cashier"])),
) -> ChargeOrderOut:
    try:
        return charge_service.charge_prescription(db, current_user, payload)
    except charge_service.ChargeServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
