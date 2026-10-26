from datetime import date, datetime, time, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.charge_order import ChargeOrder
from app.models.registration import Registration


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
