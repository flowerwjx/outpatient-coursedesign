from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.config import CORS_ALLOW_ORIGINS
from app.database import Base, engine
import app.models  # noqa: F401  (register ORM models with Base)
from app.middleware.audit import AuditMiddleware
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
from app.routers.statistics import (
    dashboard_router,
    router as statistics_router,
)

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
app.include_router(audit_router)
app.include_router(doctor_router)
app.include_router(doctor_workbench_router)
app.include_router(schedule_router)
app.include_router(registration_router)
app.include_router(prescription_router)
app.include_router(charge_router)
app.include_router(drug_router)
app.include_router(dispense_router)
app.include_router(statistics_router)
app.include_router(dashboard_router)


STATIC_DIR = Path(__file__).resolve().parents[1] / "static"

if STATIC_DIR.is_dir():
    assets_dir = STATIC_DIR / "assets"
    if assets_dir.is_dir():
        app.mount(
            "/assets",
            StaticFiles(directory=assets_dir),
            name="assets",
        )

    @app.get("/", include_in_schema=False)
    def serve_index():
        return FileResponse(STATIC_DIR / "index.html")

    @app.get("/{full_path:path}", include_in_schema=False)
    def serve_spa(full_path: str):
        if full_path == "api" or full_path.startswith("api/"):
            raise HTTPException(status_code=404, detail="Not Found")

        target = (STATIC_DIR / full_path).resolve()
        if target.is_file() and target.is_relative_to(STATIC_DIR):
            return FileResponse(target)

        return FileResponse(STATIC_DIR / "index.html")
