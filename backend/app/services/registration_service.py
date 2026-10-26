from datetime import date
from typing import Optional, Sequence

from sqlalchemy import update
from sqlalchemy.orm import Session

from app.models.registration import Registration, RegistrationStatus
from app.models.schedule import Schedule
from app.schemas.registration import RegistrationCreate


class RegistrationServiceError(Exception):
    status_code = 400

    def __init__(self, detail: str) -> None:
        super().__init__(detail)
        self.detail = detail


class RegistrationScheduleNotFoundError(RegistrationServiceError):
    status_code = 404


class QuotaExhaustedError(RegistrationServiceError):
    status_code = 400


def create_registration(db: Session, payload: RegistrationCreate) -> Registration:
    schedule_id = payload.schedule_id
    if db.query(Schedule.id).filter(Schedule.id == schedule_id).first() is None:
        raise RegistrationScheduleNotFoundError("schedule not found")

    # Atomic quota deduction: the WHERE clause guarantees the quota never
    # becomes negative even when two requests race for the last slot.
    result = db.execute(
        update(Schedule)
        .where(Schedule.id == schedule_id, Schedule.remaining_quota > 0)
        .values(remaining_quota=Schedule.remaining_quota - 1)
        .execution_options(synchronize_session=False)
    )

    if result.rowcount != 1:
        # The registration record was not inserted, so rolling back only
        # releases the failed deduction attempt.
        db.rollback()
        if db.query(Schedule.id).filter(Schedule.id == schedule_id).first() is None:
            raise RegistrationScheduleNotFoundError("schedule not found")
        raise QuotaExhaustedError("no available quota for this schedule")

    registration = Registration(
        patient_name=payload.patient_name,
        phone=payload.phone,
        schedule_id=schedule_id,
        status=RegistrationStatus.REGISTERED,
    )
    db.add(registration)
    try:
        # The deduction and the registration record are committed together.
        db.commit()
    except Exception:
        db.rollback()
        raise
    db.refresh(registration)
    return registration


def list_registrations(
    db: Session,
    schedule_date: Optional[date] = None,
    schedule_id: Optional[int] = None,
    phone: Optional[str] = None,
    patient_name: Optional[str] = None,
    limit: int = 100,
) -> Sequence[Registration]:
    query = db.query(Registration)
    if schedule_date is not None:
        query = query.filter(
            Registration.schedule.has(Schedule.schedule_date == schedule_date)
        )
    if schedule_id is not None:
        query = query.filter(Registration.schedule_id == schedule_id)
    if phone:
        query = query.filter(Registration.phone.contains(phone.strip()))
    if patient_name:
        query = query.filter(Registration.patient_name.contains(patient_name.strip()))
    return (
        query.order_by(Registration.created_at.desc(), Registration.id.desc())
        .limit(limit)
        .all()
    )
