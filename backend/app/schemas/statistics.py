from datetime import date

from pydantic import BaseModel


class DailyStatisticsOut(BaseModel):
    date: date
    registration_count: int
    charge_total_amount: float
