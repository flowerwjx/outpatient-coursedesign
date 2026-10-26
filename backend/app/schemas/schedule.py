from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class ScheduleCreate(BaseModel):
    department: str = Field(..., min_length=1, max_length=100)
    doctor_id: int = Field(..., gt=0)
    schedule_date: date
    max_quota: int = Field(..., ge=1, le=10000)

    @field_validator("department")
    @classmethod
    def _strip_department(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("department must not be blank")
        return value


class ScheduleUpdate(BaseModel):
    department: Optional[str] = Field(default=None, min_length=1, max_length=100)
    doctor_id: Optional[int] = Field(default=None, gt=0)
    schedule_date: Optional[date] = None
    max_quota: Optional[int] = Field(default=None, ge=1, le=10000)

    @field_validator("department")
    @classmethod
    def _strip_department(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        value = value.strip()
        if not value:
            raise ValueError("department must not be blank")
        return value

    @model_validator(mode="after")
    def _require_at_least_one_field(self) -> "ScheduleUpdate":
        if all(
            value is None
            for value in (
                self.department,
                self.doctor_id,
                self.schedule_date,
                self.max_quota,
            )
        ):
            raise ValueError("at least one field must be provided")
        return self


class ScheduleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    department: str
    doctor_id: int
    doctor_username: Optional[str] = None
    schedule_date: date
    max_quota: int
    remaining_quota: int
    used_quota: int
    created_at: datetime
    updated_at: datetime
