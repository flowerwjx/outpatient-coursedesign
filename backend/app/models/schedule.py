from sqlalchemy import (
    CheckConstraint,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import relationship

from app.database import Base


class Schedule(Base):
    __tablename__ = "schedules"
    __table_args__ = (
        CheckConstraint("max_quota > 0", name="ck_schedules_max_quota_positive"),
        CheckConstraint(
            "remaining_quota >= 0", name="ck_schedules_remaining_non_negative"
        ),
        CheckConstraint(
            "remaining_quota <= max_quota",
            name="ck_schedules_remaining_within_max",
        ),
        UniqueConstraint(
            "doctor_id",
            "department",
            "schedule_date",
            name="uq_schedules_doctor_department_date",
        ),
        Index("ix_schedules_date_department", "schedule_date", "department"),
    )

    id = Column(Integer, primary_key=True, index=True)
    department = Column(String(100), nullable=False, index=True)
    doctor_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    schedule_date = Column(Date, nullable=False, index=True)
    max_quota = Column(Integer, nullable=False)
    remaining_quota = Column(Integer, nullable=False)
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    doctor = relationship("User", lazy="joined")

    @property
    def doctor_username(self):
        return self.doctor.username if self.doctor else None

    @property
    def used_quota(self) -> int:
        return (self.max_quota or 0) - (self.remaining_quota or 0)

    def __repr__(self) -> str:
        return (
            f"<Schedule id={self.id} department={self.department!r} "
            f"doctor_id={self.doctor_id} date={self.schedule_date} "
            f"remaining={self.remaining_quota}/{self.max_quota}>"
        )
