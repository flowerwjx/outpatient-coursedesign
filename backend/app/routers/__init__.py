from app.routers.audit import router as audit_router
from app.routers.auth import router as auth_router
from app.routers.charge import router as charge_router
from app.routers.dispense import router as dispense_router
from app.routers.doctor import router as doctor_router
from app.routers.drug import router as drug_router
from app.routers.prescription import (
    router as prescription_router,
    workbench_router as doctor_workbench_router,
)
from app.routers.registration import router as registration_router
from app.routers.schedule import router as schedule_router
from app.routers.statistics import router as statistics_router

__all__ = [
    "audit_router",
    "auth_router",
    "charge_router",
    "dispense_router",
    "doctor_router",
    "doctor_workbench_router",
    "drug_router",
    "prescription_router",
    "registration_router",
    "schedule_router",
    "statistics_router",
]
