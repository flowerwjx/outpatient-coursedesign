from sqlalchemy import update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.dispense_record import DispenseRecord
from app.models.drug import Drug
from app.models.prescription import Prescription, PrescriptionItem
from app.models.user import User
from app.schemas.dispense import DispenseCreate


class DispenseServiceError(Exception):
    status_code = 400

    def __init__(self, detail: str) -> None:
        super().__init__(detail)
        self.detail = detail


class PrescriptionNotFoundError(DispenseServiceError):
    status_code = 404


class PrescriptionNotPaidError(DispenseServiceError):
    status_code = 400


class PrescriptionAlreadyDispensedError(DispenseServiceError):
    status_code = 409


class DrugNotFoundError(DispenseServiceError):
    status_code = 400


class InvalidDispenseDataError(DispenseServiceError):
    status_code = 400


class InsufficientStockError(DispenseServiceError):
    status_code = 400


class DispenseConflictError(DispenseServiceError):
    status_code = 409


def deduct_stock(db: Session, drug_id: int, qty: int) -> int:
    try:
        quantity = int(qty)
    except (TypeError, ValueError) as exc:
        raise InvalidDispenseDataError(
            "quantity must be a positive integer"
        ) from exc

    if quantity <= 0:
        raise InvalidDispenseDataError(
            "quantity must be a positive integer"
        )

    result = db.execute(
        update(Drug)
        .where(
            Drug.id == drug_id,
            Drug.stock >= quantity,
        )
        .values(stock=Drug.stock - quantity)
        .execution_options(synchronize_session=False)
    )
    if result.rowcount != 1:
        drug = db.get(Drug, drug_id)
        if drug is None:
            raise DrugNotFoundError(
                f"drug {drug_id} not found in drug archive"
            )
        raise InsufficientStockError(
            f"insufficient stock for drug {drug.generic_name}"
        )

    return quantity


def dispense_prescription(
    db: Session, pharmacist: User, payload: DispenseCreate
) -> dict:
    prescription = db.get(Prescription, payload.prescription_id)
    if prescription is None:
        raise PrescriptionNotFoundError("prescription not found")

    if not prescription.paid:
        raise PrescriptionNotPaidError(
            "prescription must be paid before dispensing"
        )

    existing = (
        db.query(DispenseRecord.id)
        .filter(DispenseRecord.prescription_id == prescription.id)
        .first()
    )
    if existing is not None:
        raise PrescriptionAlreadyDispensedError(
            "prescription has already been dispensed"
        )

    items = (
        db.query(PrescriptionItem)
        .filter(PrescriptionItem.prescription_id == prescription.id)
        .order_by(PrescriptionItem.id.asc())
        .all()
    )
    if not items:
        raise InvalidDispenseDataError("prescription has no items")

    drug_ids = [item.drug_id for item in items]
    drugs = db.query(Drug).filter(Drug.id.in_(drug_ids)).all()
    drug_map = {drug.id: drug for drug in drugs}

    for item in items:
        drug = drug_map.get(item.drug_id)
        if drug is None:
            raise DrugNotFoundError(
                f"drug {item.drug_id} not found in drug archive"
            )
        if item.qty is None or int(item.qty) <= 0:
            raise InvalidDispenseDataError(
                f"invalid quantity for drug {drug.generic_name}"
            )
        if drug.stock < int(item.qty):
            raise InsufficientStockError(
                f"insufficient stock for drug {drug.generic_name}: "
                f"required {int(item.qty)}, available {drug.stock}"
            )

    try:
        for item in items:
            deduct_stock(db, item.drug_id, item.qty)
    except DispenseServiceError:
        db.rollback()
        raise

    record = DispenseRecord(
        prescription_id=prescription.id,
        pharmacist_id=pharmacist.id,
    )
    db.add(record)

    try:
        # Stock deductions and the dispense record are committed together.
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        existing = (
            db.query(DispenseRecord.id)
            .filter(DispenseRecord.prescription_id == prescription.id)
            .first()
        )
        if existing is not None:
            raise PrescriptionAlreadyDispensedError(
                "prescription has already been dispensed"
            ) from exc
        raise DispenseConflictError("failed to create dispense record") from exc

    db.refresh(record)

    refreshed_drugs = db.query(Drug).filter(Drug.id.in_(drug_ids)).all()
    refreshed_map = {drug.id: drug for drug in refreshed_drugs}
    lines = []
    for item in items:
        drug = refreshed_map.get(item.drug_id)
        lines.append(
            {
                "drug_id": item.drug_id,
                "generic_name": drug.generic_name if drug else "-",
                "spec": drug.spec if drug else "-",
                "qty": int(item.qty),
                "remaining_stock": drug.stock if drug else 0,
            }
        )

    return {
        "id": record.id,
        "prescription_id": record.prescription_id,
        "pharmacist_id": record.pharmacist_id,
        "pharmacist_username": record.pharmacist_username,
        "dispensed_at": record.dispensed_at,
        "patient_name": record.patient_name,
        "department": record.department,
        "schedule_date": record.schedule_date,
        "doctor_username": record.doctor_username,
        "items": lines,
    }
