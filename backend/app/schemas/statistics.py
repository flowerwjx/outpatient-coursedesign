from datetime import date

from pydantic import BaseModel


class DailyStatisticsOut(BaseModel):
    date: date
    registration_count: int
    charge_total_amount: float


class DashboardMetricsOut(BaseModel):
    registration_count: int
    charge_total_amount: float
    dispense_count: int
    low_stock_count: int


class RegistrationTrendItem(BaseModel):
    date: date
    count: int


class DepartmentRegistrationItem(BaseModel):
    department: str
    count: int


class TopDrugItem(BaseModel):
    drug_id: int
    drug_name: str
    count: int


class LowStockDrugItem(BaseModel):
    id: int
    generic_name: str
    spec: str
    stock: int


class DashboardOut(BaseModel):
    date: date
    metrics: DashboardMetricsOut
    registration_trend: list[RegistrationTrendItem]
    department_distribution: list[DepartmentRegistrationItem]
    top_drugs: list[TopDrugItem]
    low_stock_drugs: list[LowStockDrugItem]
