from app.routers.auth import router as auth_router
from app.routers.doctor import router as doctor_router
from app.routers.registration import router as registration_router
from app.routers.schedule import router as schedule_router

__all__ = [
    "auth_router",
    "doctor_router",
    "registration_router",
    "schedule_router",
]
