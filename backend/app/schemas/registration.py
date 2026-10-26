from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.registration import RegistrationStatus


class RegistrationCreate(BaseModel):
    patient_name: str = Field(..., min_length=1, max_length=50)
    phone: str = Field(..., pattern=r"^1[3-9]\d{9}$")
    schedule_id: int = Field(..., gt=0)

    @field_validator("patient_name")
    @classmethod
    def _strip_patient_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("patient_name must not be blank")
        return value


class RegistrationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    patient_name: str
    phone: str
    schedule_id: int
    status: RegistrationStatus
    created_at: datetime
    department: Optional[str] = None
    schedule_date: Optional[date] = None
    doctor_username: Optional[str] = None
