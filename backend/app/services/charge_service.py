from datetime import date, datetime, time, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Optional, Sequence

from sqlalchemy import update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.charge_order import ChargeOrder
from app.models.drug import Drug
from app.models.prescription import Prescription, PrescriptionItem
from app.models.user import User
from app.schemas.charge import ChargeCreate


class ChargeServiceError(Exception):
    status_code = 400

    def __init__(self, detail: str) -> None:
        super().__init__(detail)
        self.detail = detail


class PrescriptionNotFoundError(ChargeServiceError):
    status_code = 404


class PrescriptionAlreadyPaidError(ChargeServiceError):
    status_code = 409


class DrugNotFoundError(ChargeServiceError):
    status_code = 400


class InvalidChargeDataError(ChargeServiceError):
    status_code = 400


class ChargeConflictError(ChargeServiceError):
    status_code = 409


def _priced_items(
    db: Session, prescription: Prescription
) -> tuple[Decimal, list[dict]]:
    items = (
        db.query(PrescriptionItem)
        .filter(PrescriptionItem.prescription_id == prescription.id)
        .all()
    )
    if not items:
        raise InvalidChargeDataError("prescription has no items")

    drug_ids = {item.drug_id for item in items}
    drugs = db.query(Drug).filter(Drug.id.in_(drug_ids)).all()
    drug_map = {drug.id: drug for drug in drugs}

    total = Decimal("0.00")
    lines: list[dict] = []
    for item in items:
        drug = drug_map.get(item.drug_id)
        if drug is None:
            raise DrugNotFoundError(
                f"drug {item.drug_id} not found in drug archive"
            )
        if item.qty is None or int(item.qty) <= 0:
            raise InvalidChargeDataError(
                f"invalid quantity for drug {item.drug_id}"
            )

        qty = int(item.qty)
        unit_price = Decimal(str(drug.unit_price)).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
        line_total = (unit_price * qty).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
        total += line_total
        lines.append(
            {
                "drug_id": drug.id,
                "generic_name": drug.generic_name,
                "trade_name": drug.trade_name,
                "spec": drug.spec,
                "dosage_form": drug.dosage_form,
                "insurance_type": drug.insurance_type,
                "qty": qty,
                "unit_price": float(unit_price),
                "line_total": float(line_total),
            }
        )

    return total.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP), lines


def _calculate_total(db: Session, prescription: Prescription) -> Decimal:
    total, _ = _priced_items(db, prescription)
    return total


def preview_charge(db: Session, prescription_id: int) -> dict:
    prescription = db.get(Prescription, prescription_id)
    if prescription is None:
        raise PrescriptionNotFoundError("prescription not found")
    if prescription.paid:
        raise PrescriptionAlreadyPaidError("prescription is already paid")

    total_amount, lines = _priced_items(db, prescription)
    return {
        "prescription_id": prescription.id,
        "patient_name": prescription.patient_name,
        "patient_phone": prescription.patient_phone,
        "department": prescription.department,
        "schedule_date": prescription.schedule_date,
        "doctor_username": prescription.doctor_username,
        "icd10_code": prescription.icd10_code,
        "diagnosis_name": prescription.diagnosis_name,
        "total_amount": float(total_amount),
        "items": lines,
    }


def list_charge_orders(
    db: Session,
    charged_date: Optional[date] = None,
    limit: int = 100,
) -> Sequence[ChargeOrder]:
    query = db.query(ChargeOrder)
    if charged_date is not None:
        start = datetime.combine(charged_date, time.min)
        end = start + timedelta(days=1)
        query = query.filter(
            ChargeOrder.charged_at >= start,
            ChargeOrder.charged_at < end,
        )
    return (
        query.order_by(ChargeOrder.charged_at.desc(), ChargeOrder.id.desc())
        .limit(limit)
        .all()
    )


def charge_prescription(
    db: Session, cashier: User, payload: ChargeCreate
) -> ChargeOrder:
    prescription = db.get(Prescription, payload.prescription_id)
    if prescription is None:
        raise PrescriptionNotFoundError("prescription not found")

    if prescription.paid:
        raise PrescriptionAlreadyPaidError("prescription is already paid")

    total_amount = _calculate_total(db, prescription)

    # Atomic status transition: only an unpaid prescription can be marked paid.
    # This prevents two concurrent requests from both creating a charge order.
    result = db.execute(
        update(Prescription)
        .where(
            Prescription.id == prescription.id,
            Prescription.paid.is_(False),
        )
        .values(paid=True)
        .execution_options(synchronize_session=False)
    )

    if result.rowcount != 1:
        db.rollback()
        current = (
            db.query(Prescription.paid)
            .filter(Prescription.id == prescription.id)
            .first()
        )
        if current is None:
            raise PrescriptionNotFoundError("prescription not found")
        raise PrescriptionAlreadyPaidError("prescription is already paid")

    charge_order = ChargeOrder(
        prescription_id=prescription.id,
        total_amount=total_amount,
        cashier_id=cashier.id,
    )
    db.add(charge_order)

    try:
        # Charge order creation and the paid flag update are one transaction.
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        existing = (
            db.query(ChargeOrder.id)
            .filter(ChargeOrder.prescription_id == prescription.id)
            .first()
        )
        if existing is not None:
            raise PrescriptionAlreadyPaidError(
                "prescription already has a charge order"
            ) from exc
        raise ChargeConflictError("failed to create charge order") from exc

    db.refresh(charge_order)
    return charge_order
