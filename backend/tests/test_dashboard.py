import os
import sys
import tempfile
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from pathlib import Path

_TMP_DIR = tempfile.mkdtemp(prefix="his_dashboard_test_")
os.environ["DATABASE_URL"] = "sqlite:///" + (
    Path(_TMP_DIR) / "test_dashboard.db"
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
from app.models.dispense_record import DispenseRecord
from app.models.drug import Drug
from app.models.prescription import Prescription, PrescriptionItem
from app.models.registration import Registration
from app.models.schedule import Schedule
from app.models.user import User, UserRole
from app.services.statistics_service import get_dashboard_statistics
from app.services.user_service import create_user


@pytest.fixture(scope="module")
def client():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        create_user(
            db, username="admin", password="admin123", role=UserRole.ADMIN
        )
        create_user(
            db, username="doctor", password="doc123", role=UserRole.DOCTOR
        )
        doctor = db.query(User).filter_by(username="doctor").first()
        cashier = create_user(
            db, username="cashier", password="cash123", role=UserRole.CASHIER
        )
        pharmacist = create_user(
            db, username="pharmacist", password="pha123", role=UserRole.PHARMACIST
        )

        today = date.today()
        today_noon = datetime.combine(today, time(12, 0, 0))
        yesterday_noon = datetime.combine(
            today - timedelta(days=1), time(12, 0, 0)
        )
        three_days_ago_noon = datetime.combine(
            today - timedelta(days=3), time(12, 0, 0)
        )

        internal_today = Schedule(
            department="内科",
            doctor_id=doctor.id,
            schedule_date=today,
            max_quota=100,
            remaining_quota=100,
        )
        surgery_today = Schedule(
            department="外科",
            doctor_id=doctor.id,
            schedule_date=today,
            max_quota=100,
            remaining_quota=100,
        )
        internal_yesterday = Schedule(
            department="内科",
            doctor_id=doctor.id,
            schedule_date=today - timedelta(days=1),
            max_quota=100,
            remaining_quota=100,
        )
        internal_three_days_ago = Schedule(
            department="内科",
            doctor_id=doctor.id,
            schedule_date=today - timedelta(days=3),
            max_quota=100,
            remaining_quota=100,
        )
        db.add_all(
            [
                internal_today,
                surgery_today,
                internal_yesterday,
                internal_three_days_ago,
            ]
        )
        db.commit()

        registrations = [
            Registration(
                patient_name="今日内科一",
                phone="13800138001",
                schedule_id=internal_today.id,
                created_at=today_noon,
            ),
            Registration(
                patient_name="今日内科二",
                phone="13800138002",
                schedule_id=internal_today.id,
                created_at=today_noon + timedelta(hours=1),
            ),
            Registration(
                patient_name="今日外科",
                phone="13800138003",
                schedule_id=surgery_today.id,
                created_at=today_noon + timedelta(hours=2),
            ),
            Registration(
                patient_name="昨日内科",
                phone="13800138004",
                schedule_id=internal_yesterday.id,
                created_at=yesterday_noon,
            ),
            Registration(
                patient_name="三日前内科",
                phone="13800138005",
                schedule_id=internal_three_days_ago.id,
                created_at=three_days_ago_noon,
            ),
        ]
        db.add_all(registrations)
        db.commit()
        for item in registrations:
            db.refresh(item)

        drug_a = Drug(
            generic_name="热门药品A",
            trade_name="商品A",
            spec="10mg×10片",
            dosage_form="片剂",
            insurance_type="甲类",
            unit_price=Decimal("10.00"),
            stock=100,
        )
        drug_b = Drug(
            generic_name="低库存药品B",
            trade_name="商品B",
            spec="20mg×20片",
            dosage_form="胶囊剂",
            insurance_type="乙类",
            unit_price=Decimal("5.00"),
            stock=15,
        )
        drug_c = Drug(
            generic_name="低库存药品C",
            trade_name="商品C",
            spec="5mg×5片",
            dosage_form="片剂",
            insurance_type="甲类",
            unit_price=Decimal("3.00"),
            stock=5,
        )
        drug_d = Drug(
            generic_name="普通药品D",
            trade_name="商品D",
            spec="1g×6袋",
            dosage_form="散剂",
            insurance_type="甲类",
            unit_price=Decimal("8.00"),
            stock=100,
        )
        drug_e = Drug(
            generic_name="低库存药品E",
            trade_name="商品E",
            spec="100ml",
            dosage_form="口服溶液",
            insurance_type="乙类",
            unit_price=Decimal("12.00"),
            stock=19,
        )
        db.add_all([drug_a, drug_b, drug_c, drug_d, drug_e])
        db.commit()

        prescriptions = []
        for registration in registrations:
            prescription = Prescription(
                registration_id=registration.id,
                doctor_id=doctor.id,
                icd10_code="J06.9",
                diagnosis_name="急性上呼吸道感染",
                paid=registration.id in {
                    registrations[0].id,
                    registrations[1].id,
                },
            )
            prescriptions.append(prescription)
        db.add_all(prescriptions)
        db.commit()
        for prescription in prescriptions:
            db.refresh(prescription)

        db.add_all(
            [
                PrescriptionItem(
                    prescription_id=prescriptions[0].id,
                    drug_id=drug_a.id,
                    qty=2,
                ),
                PrescriptionItem(
                    prescription_id=prescriptions[0].id,
                    drug_id=drug_b.id,
                    qty=1,
                ),
                PrescriptionItem(
                    prescription_id=prescriptions[1].id,
                    drug_id=drug_a.id,
                    qty=1,
                ),
                PrescriptionItem(
                    prescription_id=prescriptions[2].id,
                    drug_id=drug_c.id,
                    qty=1,
                ),
                PrescriptionItem(
                    prescription_id=prescriptions[3].id,
                    drug_id=drug_a.id,
                    qty=1,
                ),
                PrescriptionItem(
                    prescription_id=prescriptions[4].id,
                    drug_id=drug_d.id,
                    qty=1,
                ),
            ]
        )
        db.commit()

        db.add_all(
            [
                ChargeOrder(
                    prescription_id=prescriptions[0].id,
                    total_amount=Decimal("28.20"),
                    cashier_id=cashier.id,
                    charged_at=today_noon,
                ),
                ChargeOrder(
                    prescription_id=prescriptions[1].id,
                    total_amount=Decimal("10.00"),
                    cashier_id=cashier.id,
                    charged_at=today_noon + timedelta(hours=1),
                ),
                DispenseRecord(
                    prescription_id=prescriptions[0].id,
                    pharmacist_id=pharmacist.id,
                    dispensed_at=today_noon + timedelta(hours=2),
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


def test_dashboard_returns_metrics_charts_and_warnings(client, admin_headers):
    response = client.get("/api/stats/dashboard", headers=admin_headers)

    assert response.status_code == 200, response.text
    body = response.json()

    assert body["date"] == date.today().isoformat()
    metrics = body["metrics"]
    assert metrics["registration_count"] == 3
    assert metrics["charge_total_amount"] == pytest.approx(38.20)
    assert metrics["dispense_count"] == 1
    assert metrics["low_stock_count"] == 3

    trend = body["registration_trend"]
    assert len(trend) == 7
    assert trend[0]["date"] == (date.today() - timedelta(days=6)).isoformat()
    assert trend[-1]["date"] == date.today().isoformat()
    assert trend[-1]["count"] == 3
    assert trend[-2]["count"] == 1
    assert trend[-4]["count"] == 1

    departments = {
        item["department"]: item["count"]
        for item in body["department_distribution"]
    }
    assert departments == {"内科": 2, "外科": 1}

    top_drugs = body["top_drugs"]
    assert top_drugs[0]["drug_name"] == "热门药品A"
    assert top_drugs[0]["count"] == 3
    assert {item["drug_name"] for item in top_drugs} == {
        "热门药品A",
        "低库存药品B",
        "低库存药品C",
        "普通药品D",
    }

    low_stock = body["low_stock_drugs"]
    assert [item["generic_name"] for item in low_stock] == [
        "低库存药品C",
        "低库存药品B",
        "低库存药品E",
    ]
    assert [item["stock"] for item in low_stock] == [5, 15, 19]


def test_dashboard_requires_admin(client, cashier_headers, doctor_headers):
    assert (
        client.get("/api/stats/dashboard", headers=cashier_headers).status_code
        == 403
    )
    assert (
        client.get("/api/stats/dashboard", headers=doctor_headers).status_code
        == 403
    )
    assert client.get("/api/stats/dashboard").status_code == 401


def test_dashboard_empty_future_date():
    db = SessionLocal()
    try:
        stats = get_dashboard_statistics(
            db, date.today() + timedelta(days=30)
        )
    finally:
        db.close()

    assert stats["metrics"] == {
        "registration_count": 0,
        "charge_total_amount": 0.0,
        "dispense_count": 0,
        "low_stock_count": 3,
    }
    assert all(item["count"] == 0 for item in stats["registration_trend"])
    assert stats["department_distribution"] == []
    assert stats["top_drugs"]
