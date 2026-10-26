import os
import sys
import tempfile
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from pathlib import Path

_TMP_DIR = tempfile.mkdtemp(prefix="his_statistics_test_")
os.environ["DATABASE_URL"] = "sqlite:///" + (
    Path(_TMP_DIR) / "test_statistics.db"
).as_posix()
os.environ.setdefault("JWT_SECRET", "test-only-secret")

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import pytest
from fastapi.testclient import TestClient

from app.database import Base, SessionLocal, engine
from app.main import app
from app.models.charge_order import ChargeOrder
from app.models.prescription import Prescription
from app.models.registration import Registration
from app.models.schedule import Schedule
from app.models.user import UserRole
from app.services.statistics_service import get_daily_statistics
from app.services.user_service import create_user


@pytest.fixture(scope="module")
def client():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        admin = create_user(
            db, username="admin", password="admin123", role=UserRole.ADMIN
        )
        cashier = create_user(
            db, username="cashier", password="cash123", role=UserRole.CASHIER
        )
        doctor = create_user(
            db, username="doctor", password="doc123", role=UserRole.DOCTOR
        )

        schedule = Schedule(
            department="内科",
            doctor_id=doctor.id,
            schedule_date=date.today(),
            max_quota=100,
            remaining_quota=100,
        )
        db.add(schedule)
        db.commit()
        db.refresh(schedule)

        today = date.today()
        today_noon = datetime.combine(today, time(12, 0, 0))
        yesterday_noon = datetime.combine(
            today - timedelta(days=1), time(12, 0, 0)
        )

        today_registration_one = Registration(
            patient_name="今日患者一",
            phone="13800138001",
            schedule_id=schedule.id,
            created_at=today_noon,
        )
        today_registration_two = Registration(
            patient_name="今日患者二",
            phone="13800138002",
            schedule_id=schedule.id,
            created_at=today_noon + timedelta(hours=1),
        )
        yesterday_registration = Registration(
            patient_name="昨日患者",
            phone="13800138003",
            schedule_id=schedule.id,
            created_at=yesterday_noon,
        )
        db.add_all(
            [
                today_registration_one,
                today_registration_two,
                yesterday_registration,
            ]
        )
        db.commit()
        db.refresh(today_registration_one)
        db.refresh(today_registration_two)
        db.refresh(yesterday_registration)

        today_prescription_one = Prescription(
            registration_id=today_registration_one.id,
            doctor_id=doctor.id,
            icd10_code="J06.9",
            diagnosis_name="急性上呼吸道感染",
            paid=True,
        )
        today_prescription_two = Prescription(
            registration_id=today_registration_two.id,
            doctor_id=doctor.id,
            icd10_code="J06.9",
            diagnosis_name="急性上呼吸道感染",
            paid=True,
        )
        yesterday_prescription = Prescription(
            registration_id=yesterday_registration.id,
            doctor_id=doctor.id,
            icd10_code="J06.9",
            diagnosis_name="急性上呼吸道感染",
            paid=True,
        )
        db.add_all(
            [
                today_prescription_one,
                today_prescription_two,
                yesterday_prescription,
            ]
        )
        db.commit()
        db.refresh(today_prescription_one)
        db.refresh(today_prescription_two)
        db.refresh(yesterday_prescription)

        db.add_all(
            [
                ChargeOrder(
                    prescription_id=today_prescription_one.id,
                    total_amount=Decimal("28.20"),
                    cashier_id=cashier.id,
                    charged_at=today_noon,
                ),
                ChargeOrder(
                    prescription_id=today_prescription_two.id,
                    total_amount=Decimal("10.00"),
                    cashier_id=cashier.id,
                    charged_at=today_noon + timedelta(hours=1),
                ),
                ChargeOrder(
                    prescription_id=yesterday_prescription.id,
                    total_amount=Decimal("99.99"),
                    cashier_id=cashier.id,
                    charged_at=yesterday_noon,
                ),
            ]
        )
        db.commit()
    finally:
        db.close()

    with TestClient(app) as test_client:
        yield test_client

    Base.metadata.drop_all(bind=engine)


def _login(client: TestClient, username: str, password: str) -> str:
    response = client.post(
        "/api/auth/login", json={"username": username, "password": password}
    )
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="module")
def admin_headers(client):
    return _headers(_login(client, "admin", "admin123"))


@pytest.fixture(scope="module")
def cashier_headers(client):
    return _headers(_login(client, "cashier", "cash123"))


@pytest.fixture(scope="module")
def doctor_headers(client):
    return _headers(_login(client, "doctor", "doc123"))


def test_today_statistics_counts_registrations_and_charge_amount(
    client, admin_headers
):
    response = client.get("/api/statistics/today", headers=admin_headers)

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["date"] == date.today().isoformat()
    assert body["registration_count"] == 2
    assert body["charge_total_amount"] == pytest.approx(38.20)


def test_today_statistics_requires_admin(
    client, cashier_headers, doctor_headers
):
    assert (
        client.get("/api/statistics/today", headers=cashier_headers).status_code
        == 403
    )
    assert (
        client.get("/api/statistics/today", headers=doctor_headers).status_code
        == 403
    )
    assert client.get("/api/statistics/today").status_code == 401


def test_statistics_returns_zero_for_empty_day():
    db = SessionLocal()
    try:
        stats = get_daily_statistics(
            db, date.today() + timedelta(days=10)
        )
    finally:
        db.close()

    assert stats["registration_count"] == 0
    assert stats["charge_total_amount"] == 0.0
