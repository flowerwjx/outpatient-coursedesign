from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import relationship

from app.database import Base


class ChargeOrder(Base):
    __tablename__ = "charge_orders"
    __table_args__ = (
        UniqueConstraint(
            "prescription_id", name="uq_charge_orders_prescription"
        ),
        CheckConstraint(
            "total_amount >= 0", name="ck_charge_orders_total_non_negative"
        ),
        Index(
            "ix_charge_orders_cashier_charged_at",
            "cashier_id",
            "charged_at",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    prescription_id = Column(
        Integer, ForeignKey("prescriptions.id"), nullable=False, index=True
    )
    total_amount = Column(Numeric(12, 2), nullable=False)
    cashier_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    charged_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )

    prescription = relationship("Prescription", lazy="joined")
    cashier = relationship("User", lazy="joined")

    @property
    def cashier_username(self) -> Optional[str]:
        return self.cashier.username if self.cashier else None

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

    @property
    def icd10_code(self) -> Optional[str]:
        return self.prescription.icd10_code if self.prescription else None

    @property
    def diagnosis_name(self) -> Optional[str]:
        return self.prescription.diagnosis_name if self.prescription else None

    @property
    def prescription_paid(self) -> bool:
        return bool(self.prescription.paid) if self.prescription else False

    def __repr__(self) -> str:
        return (
            f"<ChargeOrder id={self.id} prescription_id={self.prescription_id} "
            f"total_amount={self.total_amount} cashier_id={self.cashier_id}>"
        )
