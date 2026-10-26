from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class ChargeCreate(BaseModel):
    # Price fields sent by a client are intentionally not declared here.
    # Pydantic ignores unknown fields, so the backend always recalculates
    # the amount from the drug archive.
    prescription_id: int = Field(..., gt=0)


class ChargePreviewItemOut(BaseModel):
    drug_id: int
    generic_name: str
    trade_name: str = ""
    spec: str
    dosage_form: str
    insurance_type: str
    qty: int
    unit_price: float
    line_total: float


class ChargePreviewOut(BaseModel):
    prescription_id: int
    patient_name: Optional[str] = None
    patient_phone: Optional[str] = None
    department: Optional[str] = None
    schedule_date: Optional[date] = None
    doctor_username: Optional[str] = None
    icd10_code: str
    diagnosis_name: str
    total_amount: float
    items: list[ChargePreviewItemOut]


class ChargeOrderOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    prescription_id: int
    total_amount: float
    cashier_id: int
    cashier_username: Optional[str] = None
    charged_at: datetime
    patient_name: Optional[str] = None
    department: Optional[str] = None
    schedule_date: Optional[date] = None
    doctor_username: Optional[str] = None
    icd10_code: Optional[str] = None
    diagnosis_name: Optional[str] = None
    prescription_paid: bool = True
