from datetime import date
from typing import Optional

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    false,
    func,
)
from sqlalchemy.orm import relationship

from app.database import Base


class Prescription(Base):
    __tablename__ = "prescriptions"
    __table_args__ = (
        UniqueConstraint(
            "registration_id", name="uq_prescriptions_registration"
        ),
        CheckConstraint(
            "length(trim(icd10_code)) > 0",
            name="ck_prescriptions_icd10_not_blank",
        ),
        CheckConstraint(
            "length(trim(diagnosis_name)) > 0",
            name="ck_prescriptions_diagnosis_not_blank",
        ),
        Index("ix_prescriptions_doctor_paid", "doctor_id", "paid"),
    )

    id = Column(Integer, primary_key=True, index=True)
    registration_id = Column(
        Integer, ForeignKey("registrations.id"), nullable=False, index=True
    )
    doctor_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    icd10_code = Column(String(20), nullable=False)
    diagnosis_name = Column(String(200), nullable=False)
    paid = Column(
        Boolean, nullable=False, default=False, server_default=false(), index=True
    )
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    registration = relationship("Registration", lazy="joined")
    doctor = relationship("User", lazy="joined")
    items = relationship(
        "PrescriptionItem",
        back_populates="prescription",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="PrescriptionItem.id",
    )

    @property
    def patient_name(self) -> Optional[str]:
        return self.registration.patient_name if self.registration else None

    @property
    def department(self) -> Optional[str]:
        return self.registration.department if self.registration else None

    @property
    def schedule_date(self) -> Optional[date]:
        return self.registration.schedule_date if self.registration else None

    @property
    def doctor_username(self) -> Optional[str]:
        return self.doctor.username if self.doctor else None

    def __repr__(self) -> str:
        return (
            f"<Prescription id={self.id} registration_id={self.registration_id} "
            f"doctor_id={self.doctor_id} icd10={self.icd10_code!r} paid={self.paid}>"
        )


class PrescriptionItem(Base):
    __tablename__ = "prescription_items"
    __table_args__ = (
        CheckConstraint("qty > 0", name="ck_prescription_items_qty_positive"),
        UniqueConstraint(
            "prescription_id",
            "drug_id",
            name="uq_prescription_items_prescription_drug",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    prescription_id = Column(
        Integer,
        ForeignKey("prescriptions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    drug_id = Column(Integer, nullable=False, index=True)
    qty = Column(Integer, nullable=False)

    prescription = relationship("Prescription", back_populates="items")

    def __repr__(self) -> str:
        return (
            f"<PrescriptionItem id={self.id} prescription_id={self.prescription_id} "
            f"drug_id={self.drug_id} qty={self.qty}>"
        )
