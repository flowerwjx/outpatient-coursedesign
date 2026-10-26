from datetime import datetime
from typing import Optional, Sequence

from sqlalchemy.orm import Session

from app.models.audit import AuditLog


def list_audit_logs(
    db: Session,
    operator_user_id: Optional[int] = None,
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
    request_path: Optional[str] = None,
    method: Optional[str] = None,
    limit: int = 200,
) -> Sequence[dict]:
    query = db.query(AuditLog)

    if operator_user_id is not None:
        query = query.filter(AuditLog.operator_id == operator_user_id)
    if start_time is not None:
        query = query.filter(AuditLog.created_at >= start_time)
    if end_time is not None:
        query = query.filter(AuditLog.created_at <= end_time)
    if request_path:
        query = query.filter(AuditLog.path.contains(request_path.strip()))
    if method:
        query = query.filter(AuditLog.method == method.strip().upper())

    logs = (
        query.order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
        .limit(limit)
        .all()
    )

    return [
        {
            "id": log.id,
            "operator_user_id": log.operator_id,
            "operator_username": log.operator.username if log.operator else None,
            "operate_time": log.created_at,
            "request_path": log.path,
            "method": log.method,
            "status_code": log.status_code,
            "payload": log.payload,
        }
        for log in logs
    ]
