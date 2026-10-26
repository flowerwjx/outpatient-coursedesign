from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import CORS_ALLOW_ORIGINS
from app.database import Base, engine
import app.models  # noqa: F401  (register ORM models with Base)
from app.middleware.audit import AuditMiddleware
from app.routers.auth import router as auth_router
from app.routers.doctor import router as doctor_router
from app.routers.registration import router as registration_router
from app.routers.schedule import router as schedule_router

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Small Outpatient HIS API", version="0.1.0")

if CORS_ALLOW_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=CORS_ALLOW_ORIGINS,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type"],
    )

app.add_middleware(AuditMiddleware)

app.include_router(auth_router)
app.include_router(doctor_router)
app.include_router(schedule_router)
app.include_router(registration_router)
