import re
from datetime import date, datetime
from typing import Optional

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

_ICD10_PATTERN = re.compile(r"^[A-Z][0-9]{2}(\.[0-9A-Z]{1,4})?$")


class PrescriptionItemCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    drug_id: int = Field(..., gt=0)
    qty: int = Field(..., ge=1, le=100000)


class PrescriptionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    registration_id: int = Field(..., gt=0)
    icd10_code: str = Field(..., min_length=3, max_length=20)
    diagnosis_name: str = Field(..., min_length=1, max_length=200)
    items: list[PrescriptionItemCreate] = Field(..., min_length=1)

    @field_validator("icd10_code")
    @classmethod
    def _normalize_icd10_code(cls, value: str) -> str:
        normalized = value.strip().upper()
        if not _ICD10_PATTERN.fullmatch(normalized):
            raise ValueError(
                "icd10_code must follow ICD-10 format, e.g. J06.9"
            )
        return normalized

    @field_validator("diagnosis_name")
    @classmethod
    def _strip_diagnosis_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("diagnosis_name must not be blank")
        return value

    @model_validator(mode="after")
    def _require_unique_drugs(self) -> "PrescriptionCreate":
        drug_ids = [item.drug_id for item in self.items]
        if len(drug_ids) != len(set(drug_ids)):
            raise ValueError("duplicate drug_id in prescription items")
        return self


class PrescriptionItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    drug_id: int
    qty: int


class PrescriptionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    registration_id: int
    doctor_id: int
    icd10_code: str
    diagnosis_name: str
    paid: bool
    created_at: datetime
    items: list[PrescriptionItemOut]
    patient_name: Optional[str] = None
    department: Optional[str] = None
    schedule_date: Optional[date] = None
    doctor_username: Optional[str] = None
