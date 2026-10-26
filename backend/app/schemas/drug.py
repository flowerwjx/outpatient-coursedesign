from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class DrugCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    generic_name: str = Field(..., min_length=1, max_length=100)
    trade_name: str = Field(default="", max_length=100)
    spec: str = Field(..., min_length=1, max_length=100)
    dosage_form: str = Field(..., min_length=1, max_length=50)
    insurance_type: str = Field(..., min_length=1, max_length=50)
    unit_price: Decimal = Field(..., ge=0, max_digits=10, decimal_places=2)
    stock: int = Field(..., ge=0, le=100000000)

    @field_validator(
        "generic_name", "trade_name", "spec", "dosage_form", "insurance_type"
    )
    @classmethod
    def _strip_text(cls, value: str) -> str:
        return value.strip()


class DrugUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    generic_name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    trade_name: Optional[str] = Field(default=None, max_length=100)
    spec: Optional[str] = Field(default=None, min_length=1, max_length=100)
    dosage_form: Optional[str] = Field(default=None, min_length=1, max_length=50)
    insurance_type: Optional[str] = Field(default=None, min_length=1, max_length=50)
    unit_price: Optional[Decimal] = Field(
        default=None, ge=0, max_digits=10, decimal_places=2
    )
    stock: Optional[int] = Field(default=None, ge=0, le=100000000)

    @field_validator(
        "generic_name", "trade_name", "spec", "dosage_form", "insurance_type"
    )
    @classmethod
    def _strip_text(cls, value: Optional[str]) -> Optional[str]:
        return value.strip() if value is not None else None

    @model_validator(mode="after")
    def _require_at_least_one_field(self) -> "DrugUpdate":
        if all(
            value is None
            for value in (
                self.generic_name,
                self.trade_name,
                self.spec,
                self.dosage_form,
                self.insurance_type,
                self.unit_price,
                self.stock,
            )
        ):
            raise ValueError("at least one field must be provided")
        return self


class DrugOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    generic_name: str
    trade_name: str
    spec: str
    dosage_form: str
    insurance_type: str
    unit_price: float
    stock: int
    created_at: datetime
    updated_at: datetime


class DrugImportError(BaseModel):
    row: int
    error: str


class DrugImportResult(BaseModel):
    success: int
    fail: int
    errors: list[DrugImportError]
