from datetime import date, datetime, time, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.charge_order import ChargeOrder
from app.models.dispense_record import DispenseRecord
from app.models.drug import Drug
from app.models.prescription import PrescriptionItem
from app.models.registration import Registration
from app.models.schedule import Schedule

LOW_STOCK_THRESHOLD = 20


def get_daily_statistics(
    db: Session, target_date: Optional[date] = None
) -> dict:
    day = target_date or date.today()
    start = datetime.combine(day, time.min)
    end = start + timedelta(days=1)

    registration_count = (
        db.query(func.count(Registration.id))
        .filter(
            Registration.created_at >= start,
            Registration.created_at < end,
        )
        .scalar()
    )

    raw_total = (
        db.query(func.coalesce(func.sum(ChargeOrder.total_amount), 0))
        .filter(
            ChargeOrder.charged_at >= start,
            ChargeOrder.charged_at < end,
        )
        .scalar()
    )
    total_amount = Decimal(str(raw_total or 0)).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )

    return {
        "date": day,
        "registration_count": int(registration_count or 0),
        "charge_total_amount": float(total_amount),
    }


def get_dashboard_statistics(
    db: Session, target_date: Optional[date] = None
) -> dict:
    day = target_date or date.today()
    start = datetime.combine(day, time.min)
    end = start + timedelta(days=1)

    daily = get_daily_statistics(db, day)

    dispense_count = (
        db.query(func.count(DispenseRecord.id))
        .filter(
            DispenseRecord.dispensed_at >= start,
            DispenseRecord.dispensed_at < end,
        )
        .scalar()
    )

    low_stock_count = (
        db.query(func.count(Drug.id))
        .filter(Drug.stock < LOW_STOCK_THRESHOLD)
        .scalar()
    )

    trend = []
    for offset in range(6, -1, -1):
        trend_day = day - timedelta(days=offset)
        trend_start = datetime.combine(trend_day, time.min)
        trend_end = trend_start + timedelta(days=1)
        count = (
            db.query(func.count(Registration.id))
            .filter(
                Registration.created_at >= trend_start,
                Registration.created_at < trend_end,
            )
            .scalar()
        )
        trend.append({"date": trend_day, "count": int(count or 0)})

    department_count = func.count(Registration.id).label("count")
    department_rows = (
        db.query(Schedule.department, department_count)
        .join(Registration, Registration.schedule_id == Schedule.id)
        .filter(
            Registration.created_at >= start,
            Registration.created_at < end,
        )
        .group_by(Schedule.department)
        .order_by(department_count.desc(), Schedule.department.asc())
        .all()
    )

    drug_count = func.count(PrescriptionItem.id).label("count")
    top_drug_rows = (
        db.query(Drug.id, Drug.generic_name, drug_count)
        .join(PrescriptionItem, Drug.id == PrescriptionItem.drug_id)
        .group_by(Drug.id, Drug.generic_name)
        .order_by(drug_count.desc(), Drug.id.asc())
        .limit(5)
        .all()
    )

    low_stock_drugs = (
        db.query(Drug)
        .filter(Drug.stock < LOW_STOCK_THRESHOLD)
        .order_by(Drug.stock.asc(), Drug.id.asc())
        .all()
    )

    return {
        "date": day,
        "metrics": {
            "registration_count": daily["registration_count"],
            "charge_total_amount": daily["charge_total_amount"],
            "dispense_count": int(dispense_count or 0),
            "low_stock_count": int(low_stock_count or 0),
        },
        "registration_trend": trend,
        "department_distribution": [
            {"department": department, "count": int(count)}
            for department, count in department_rows
        ],
        "top_drugs": [
            {
                "drug_id": drug_id,
                "drug_name": drug_name,
                "count": int(count),
            }
            for drug_id, drug_name, count in top_drug_rows
        ],
        "low_stock_drugs": [
            {
                "id": drug.id,
                "generic_name": drug.generic_name,
                "spec": drug.spec,
                "stock": drug.stock,
            }
            for drug in low_stock_drugs
        ],
    }
