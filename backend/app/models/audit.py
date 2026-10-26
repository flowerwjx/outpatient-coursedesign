from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import relationship

from app.database import Base


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    operator_id = Column(
        "operator_user_id",
        Integer,
        ForeignKey("users.id"),
        nullable=True,
        index=True,
    )
    method = Column(String(10), nullable=False)
    path = Column("request_path", String(255), nullable=False)
    status_code = Column(Integer, nullable=False)
    payload = Column(Text, nullable=True)
    created_at = Column(
        "operate_time",
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )

    operator = relationship("User", lazy="joined")
