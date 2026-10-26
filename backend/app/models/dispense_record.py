from datetime import date, datetime
from typing import Optional

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import relationship

from app.database import Base


class DispenseRecord(Base):
    __tablename__ = "dispense_records"
    __table_args__ = (
        UniqueConstraint(
            "prescription_id", name="uq_dispense_records_prescription"
        ),
        Index(
            "ix_dispense_records_pharmacist_dispensed_at",
            "pharmacist_id",
            "dispensed_at",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    prescription_id = Column(
        Integer, ForeignKey("prescriptions.id"), nullable=False, index=True
    )
    pharmacist_id = Column(
        Integer, ForeignKey("users.id"), nullable=False, index=True
    )
    dispensed_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )

    prescription = relationship(
        "Prescription", back_populates="dispense_record", lazy="joined"
    )
    pharmacist = relationship("User", lazy="joined")

    @property
    def pharmacist_username(self) -> Optional[str]:
        return self.pharmacist.username if self.pharmacist else None

    @property
    def patient_name(self) -> Optional[str]:
        return self.prescription.patient_name if self.prescription else None

    @property
    def department(self) -> Optional[str]:
        return self.prescription.department if self.prescription else None

    @property
    def schedule_date(self) -> Optional[date]:
        return self.prescription.schedule_date if self.prescription else None

    @property
    def doctor_username(self) -> Optional[str]:
        return self.prescription.doctor_username if self.prescription else None

    def __repr__(self) -> str:
        return (
            f"<DispenseRecord id={self.id} prescription_id={self.prescription_id} "
            f"pharmacist_id={self.pharmacist_id}>"
        )
