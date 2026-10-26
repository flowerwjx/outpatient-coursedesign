from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class AuditLogOut(BaseModel):
    id: int
    operator_user_id: Optional[int] = None
    operator_username: Optional[str] = None
    operate_time: datetime
    request_path: str
    method: str
    status_code: int
    payload: Optional[str] = None
