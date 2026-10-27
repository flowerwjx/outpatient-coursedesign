from datetime import date
from typing import Optional, Sequence

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.drug import Drug
from app.models.prescription import Prescription, PrescriptionItem
from app.models.registration import Registration, RegistrationStatus
from app.models.schedule import Schedule
from app.models.user import User
from app.schemas.prescription import PrescriptionCreate


class PrescriptionServiceError(Exception):
    status_code = 400

    def __init__(self, detail: str) -> None:
        super().__init__(detail)
        self.detail = detail


class InvalidPrescriptionError(PrescriptionServiceError):
    status_code = 400


class RegistrationNotFoundError(PrescriptionServiceError):
    status_code = 404


class PrescriptionAccessDeniedError(PrescriptionServiceError):
    status_code = 403


class PrescriptionConflictError(PrescriptionServiceError):
    status_code = 409


def list_pending_registrations(
    db: Session, doctor_id: int
) -> Sequence[Registration]:
    has_prescription = (
        db.query(Prescription.id)
        .filter(Prescription.registration_id == Registration.id)
        .exists()
    )
    return (
        db.query(Registration)
        .filter(
            Registration.status == RegistrationStatus.REGISTERED,
            Registration.schedule.has(Schedule.doctor_id == doctor_id),
            ~has_prescription,
        )
        .order_by(Registration.created_at.asc(), Registration.id.asc())
        .all()
    )


def list_visited_registrations(
    db: Session,
    doctor_id: int,
    target_date: Optional[date] = None,
) -> list[dict]:
    day = target_date or date.today()
    prescriptions = (
        db.query(Prescription)
        .join(Registration, Prescription.registration_id == Registration.id)
        .join(Schedule, Registration.schedule_id == Schedule.id)
        .filter(
            Prescription.doctor_id == doctor_id,
            Schedule.schedule_date == day,
        )
        .order_by(Prescription.created_at.desc(), Prescription.id.desc())
        .all()
    )

    drug_ids = {
        item.drug_id
        for prescription in prescriptions
        for item in prescription.items
    }
    drugs = (
        db.query(Drug).filter(Drug.id.in_(drug_ids)).all() if drug_ids else []
    )
    drug_map = {drug.id: drug for drug in drugs}

    result = []
    for prescription in prescriptions:
        registration = prescription.registration
        schedule = registration.schedule if registration else None
        items = []
        for item in prescription.items:
            drug = drug_map.get(item.drug_id)
            items.append(
                {
                    "drug_id": item.drug_id,
                    "drug_name": (
                        drug.generic_name
                        if drug
                        else f"药品 #{item.drug_id}"
                    ),
                    "spec": drug.spec if drug else "-",
                    "qty": item.qty,
                }
            )

        result.append(
            {
                "registration_id": prescription.registration_id,
                "prescription_id": prescription.id,
                "patient_name": (
                    registration.patient_name if registration else ""
                ),
                "patient_phone": registration.phone if registration else None,
                "visit_date": (
                    schedule.schedule_date if schedule else day
                ),
                "visited_at": prescription.created_at,
                "icd10_code": prescription.icd10_code,
                "diagnosis_name": prescription.diagnosis_name,
                "items": items,
            }
        )

    return result


def list_prescriptions(
    db: Session,
    paid: Optional[bool] = False,
    patient_name: Optional[str] = None,
    phone: Optional[str] = None,
    limit: int = 100,
) -> Sequence[Prescription]:
    query = db.query(Prescription)
    if paid is not None:
        query = query.filter(Prescription.paid == paid)
    if patient_name:
        query = query.filter(
            Prescription.registration.has(
                Registration.patient_name.contains(patient_name.strip())
            )
        )
    if phone:
        query = query.filter(
            Prescription.registration.has(
                Registration.phone.contains(phone.strip())
            )
        )
    return (
        query.order_by(Prescription.created_at.desc(), Prescription.id.desc())
        .limit(limit)
        .all()
    )


def create_prescription(
    db: Session, doctor: User, payload: PrescriptionCreate
) -> Prescription:
    registration = db.get(Registration, payload.registration_id)
    if registration is None:
        raise RegistrationNotFoundError("registration not found")

    if (
        registration.schedule is None
        or registration.schedule.doctor_id != doctor.id
    ):
        raise PrescriptionAccessDeniedError(
            "registration does not belong to the current doctor"
        )

    if registration.status != RegistrationStatus.REGISTERED:
        raise InvalidPrescriptionError(
            "only pending registered patients can receive a prescription"
        )

    exists = (
        db.query(Prescription.id)
        .filter(Prescription.registration_id == registration.id)
        .first()
    )
    if exists is not None:
        raise PrescriptionConflictError(
            "a prescription already exists for this registration"
        )

    drug_ids = [item.drug_id for item in payload.items]
    if not drug_ids:
        raise InvalidPrescriptionError(
            "at least one prescription item is required"
        )
    if len(drug_ids) != len(set(drug_ids)):
        raise InvalidPrescriptionError(
            "duplicate drug_id in prescription items"
        )

    prescription = Prescription(
        registration_id=registration.id,
        doctor_id=doctor.id,
        icd10_code=payload.icd10_code,
        diagnosis_name=payload.diagnosis_name,
        paid=False,
        items=[
            PrescriptionItem(drug_id=item.drug_id, qty=item.qty)
            for item in payload.items
        ],
    )
    db.add(prescription)

    try:
        # Main record and all detail lines are committed together.
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        if (
            db.query(Prescription.id)
            .filter(Prescription.registration_id == registration.id)
            .first()
            is not None
        ):
            raise PrescriptionConflictError(
                "a prescription already exists for this registration"
            ) from exc
        raise InvalidPrescriptionError(
            "failed to create prescription due to invalid detail data"
        ) from exc

    db.refresh(prescription)
    _ = prescription.items  # ensure the detail lines are loaded for the response
    return prescription
