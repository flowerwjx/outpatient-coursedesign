import enum
from datetime import date
from typing import Optional

from sqlalchemy import Column, DateTime, Enum, ForeignKey, Index, Integer, String, func
from sqlalchemy.orm import relationship

from app.database import Base


class RegistrationStatus(str, enum.Enum):
    REGISTERED = "registered"
    CANCELLED = "cancelled"


class Registration(Base):
    __tablename__ = "registrations"
    __table_args__ = (
        Index("ix_registrations_schedule_status", "schedule_id", "status"),
    )

    id = Column(Integer, primary_key=True, index=True)
    patient_name = Column(String(50), nullable=False)
    phone = Column(String(20), nullable=False, index=True)
    schedule_id = Column(Integer, ForeignKey("schedules.id"), nullable=False, index=True)
    status = Column(
        Enum(
            RegistrationStatus,
            name="registration_status",
            native_enum=False,
            validate_strings=True,
            values_callable=lambda enum_cls: [item.value for item in enum_cls],
        ),
        nullable=False,
        default=RegistrationStatus.REGISTERED,
    )
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )

    schedule = relationship("Schedule", lazy="joined")

    @property
    def department(self) -> Optional[str]:
        return self.schedule.department if self.schedule else None

    @property
    def schedule_date(self) -> Optional[date]:
        return self.schedule.schedule_date if self.schedule else None

    @property
    def doctor_username(self) -> Optional[str]:
        return self.schedule.doctor_username if self.schedule else None

    def __repr__(self) -> str:
        return (
            f"<Registration id={self.id} patient={self.patient_name!r} "
            f"schedule_id={self.schedule_id} status={self.status}>"
        )
