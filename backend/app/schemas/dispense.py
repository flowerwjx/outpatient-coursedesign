from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class DispenseCreate(BaseModel):
    prescription_id: int = Field(..., gt=0)


class DispenseItemOut(BaseModel):
    drug_id: int
    generic_name: str
    spec: str
    qty: int
    remaining_stock: int


class DispenseRecordOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    prescription_id: int
    pharmacist_id: int
    pharmacist_username: Optional[str] = None
    dispensed_at: datetime
    patient_name: Optional[str] = None
    department: Optional[str] = None
    schedule_date: Optional[date] = None
    doctor_username: Optional[str] = None
    items: list[DispenseItemOut]
