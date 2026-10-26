from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.middleware.auth import require_role
from app.models.user import User
from app.schemas.audit import AuditLogOut
from app.services import audit_log_service

router = APIRouter(prefix="/api/audit-logs", tags=["audit-logs"])


@router.get("", response_model=list[AuditLogOut])
def list_audit_logs(
    operator_user_id: Optional[int] = Query(default=None, gt=0),
    start_time: Optional[datetime] = Query(default=None),
    end_time: Optional[datetime] = Query(default=None),
    request_path: Optional[str] = Query(default=None, max_length=255),
    method: Optional[str] = Query(default=None, max_length=10),
    limit: int = Query(default=200, ge=1, le=500),
    db: Session = Depends(get_db),
    _: User = Depends(require_role(["admin"])),
) -> list[AuditLogOut]:
    return list(
        audit_log_service.list_audit_logs(
            db,
            operator_user_id=operator_user_id,
            start_time=start_time,
            end_time=end_time,
            request_path=request_path,
            method=method,
            limit=limit,
        )
    )
