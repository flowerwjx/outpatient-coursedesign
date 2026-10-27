from datetime import date
from typing import Optional, Sequence

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.registration import Registration
from app.models.schedule import Schedule
from app.models.user import User, UserRole
from app.schemas.schedule import ScheduleCreate, ScheduleUpdate


class ScheduleServiceError(Exception):
    status_code = 400

    def __init__(self, detail: str) -> None:
        super().__init__(detail)
        self.detail = detail


class InvalidDoctorError(ScheduleServiceError):
    status_code = 400


class InvalidQuotaError(ScheduleServiceError):
    status_code = 400


class ScheduleNotFoundError(ScheduleServiceError):
    status_code = 404


class ScheduleConflictError(ScheduleServiceError):
    status_code = 409


def _ensure_doctor(db: Session, doctor_id: int) -> User:
    doctor = db.get(User, doctor_id)
    if doctor is None or doctor.role != UserRole.DOCTOR:
        raise InvalidDoctorError(f"doctor_id {doctor_id} is not a valid doctor")
    return doctor


def create_schedule(db: Session, payload: ScheduleCreate) -> Schedule:
    _ensure_doctor(db, payload.doctor_id)
    schedule = Schedule(
        department=payload.department,
        doctor_id=payload.doctor_id,
        schedule_date=payload.schedule_date,
        max_quota=payload.max_quota,
        remaining_quota=payload.max_quota,
    )
    db.add(schedule)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise ScheduleConflictError(
            "a schedule already exists for this doctor/department/date"
        ) from exc
    db.refresh(schedule)
    return schedule


def update_schedule(
    db: Session, schedule_id: int, payload: ScheduleUpdate
) -> Schedule:
    schedule = db.get(Schedule, schedule_id)
    if schedule is None:
        raise ScheduleNotFoundError("schedule not found")

    changes = payload.model_dump(exclude_unset=True, exclude_none=True)
    if "doctor_id" in changes:
        _ensure_doctor(db, changes["doctor_id"])

    used_quota = schedule.max_quota - schedule.remaining_quota
    new_max_quota = changes.get("max_quota", schedule.max_quota)
    if new_max_quota < used_quota:
        raise InvalidQuotaError(
            f"max_quota cannot be less than already used quota ({used_quota})"
        )

    for field, value in changes.items():
        setattr(schedule, field, value)
    schedule.remaining_quota = new_max_quota - used_quota

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise ScheduleConflictError(
            "a schedule already exists for this doctor/department/date"
        ) from exc
    db.refresh(schedule)
    return schedule


def delete_schedule(db: Session, schedule_id: int) -> None:
    schedule = db.get(Schedule, schedule_id)
    if schedule is None:
        raise ScheduleNotFoundError("schedule not found")

    registration_count = (
        db.query(func.count(Registration.id))
        .filter(Registration.schedule_id == schedule_id)
        .scalar()
    )
    if registration_count:
        raise ScheduleConflictError(
            "schedule has registration records and cannot be deleted"
        )

    db.delete(schedule)
    db.commit()


def list_schedules(
    db: Session,
    schedule_date: Optional[date] = None,
    department: Optional[str] = None,
    doctor_id: Optional[int] = None,
) -> Sequence[Schedule]:
    query = db.query(Schedule)
    if schedule_date is not None:
        query = query.filter(Schedule.schedule_date == schedule_date)
    if department:
        query = query.filter(Schedule.department == department.strip())
    if doctor_id is not None:
        query = query.filter(Schedule.doctor_id == doctor_id)
    return query.order_by(
        Schedule.schedule_date, Schedule.department, Schedule.id
    ).all()


def list_available_schedules(
    db: Session, schedule_date: date, department: Optional[str] = None
) -> Sequence[Schedule]:
    query = db.query(Schedule).filter(
        Schedule.schedule_date == schedule_date,
        Schedule.remaining_quota > 0,
    )
    if department:
        query = query.filter(Schedule.department == department.strip())
    return query.order_by(Schedule.department, Schedule.id).all()
