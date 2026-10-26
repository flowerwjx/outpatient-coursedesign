import itertools
import os
import sys
import tempfile
from datetime import date, timedelta
from pathlib import Path

_TMP_DIR = tempfile.mkdtemp(prefix="his_api_flow_test_")
os.environ["DATABASE_URL"] = "sqlite:///" + (
    Path(_TMP_DIR) / "test_api_flows.db"
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
from app.models.registration import Registration
from app.models.schedule import Schedule
from app.models.user import UserRole
from app.services.user_service import create_user

ACCOUNTS = [
    ("admin", "admin123", UserRole.ADMIN),
    ("doctor", "doc123", UserRole.DOCTOR),
    ("cashier", "cash123", UserRole.CASHIER),
    ("pharmacist", "pha123", UserRole.PHARMACIST),
]

_schedule_date_seq = itertools.count(1)
_drug_seq = itertools.count(1)


def _next_schedule_date() -> date:
    return date(2045, 1, 1) + timedelta(days=next(_schedule_date_seq))


@pytest.fixture(scope="module")
def client():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        for username, password, role in ACCOUNTS:
            create_user(db, username=username, password=password, role=role)
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
def doctor_headers(client):
    return _headers(_login(client, "doctor", "doc123"))


@pytest.fixture(scope="module")
def cashier_headers(client):
    return _headers(_login(client, "cashier", "cash123"))


@pytest.fixture(scope="module")
def pharmacist_headers(client):
    return _headers(_login(client, "pharmacist", "pha123"))


@pytest.fixture(scope="module")
def doctor_id(client, doctor_headers) -> int:
    return client.get("/api/me", headers=doctor_headers).json()["id"]


def _create_schedule(
    client: TestClient,
    admin_headers: dict,
    doctor_id: int,
    max_quota: int = 2,
) -> dict:
    payload = {
        "department": "内科",
        "doctor_id": doctor_id,
        "schedule_date": _next_schedule_date().isoformat(),
        "max_quota": max_quota,
    }
    response = client.post("/api/schedules", json=payload, headers=admin_headers)
    assert response.status_code == 201, response.text
    return response.json()


def _register(
    client: TestClient,
    headers: dict,
    schedule_id: int,
    name: str = "测试患者",
    phone: str = "13800138000",
):
    return client.post(
        "/api/registrations",
        json={"patient_name": name, "phone": phone, "schedule_id": schedule_id},
        headers=headers,
    )


def _create_drug(
    client: TestClient,
    admin_headers: dict,
    stock: int = 10,
    unit_price: str = "12.50",
) -> dict:
    number = next(_drug_seq)
    payload = {
        "generic_name": f"API测试药品{number}",
        "trade_name": f"商品名{number}",
        "spec": "10mg×10片",
        "dosage_form": "片剂",
        "insurance_type": "甲类",
        "unit_price": unit_price,
        "stock": stock,
    }
    response = client.post("/api/drugs", json=payload, headers=admin_headers)
    assert response.status_code == 201, response.text
    return response.json()


def _make_prescription(
    client: TestClient,
    admin_headers: dict,
    doctor_headers: dict,
    doctor_id: int,
    items: list[dict],
    patient_name: str = "处方测试患者",
) -> dict:
    schedule = _create_schedule(client, admin_headers, doctor_id)
    registration = _register(
        client, admin_headers, schedule["id"], name=patient_name
    )
    assert registration.status_code == 201, registration.text

    response = client.post(
        "/api/prescriptions",
        json={
            "registration_id": registration.json()["id"],
            "icd10_code": "J06.9",
            "diagnosis_name": "急性上呼吸道感染",
            "items": items,
        },
        headers=doctor_headers,
    )
    assert response.status_code == 201, response.text
    return response.json()


def _charge(client: TestClient, headers: dict, prescription_id: int, **extra):
    payload = {"prescription_id": prescription_id}
    payload.update(extra)
    return client.post("/api/charge-orders", json=payload, headers=headers)


def _dispense(client: TestClient, headers: dict, prescription_id: int):
    return client.post(
        "/api/dispenses",
        json={"prescription_id": prescription_id},
        headers=headers,
    )


def _schedule_remaining(schedule_id: int) -> int:
    db = SessionLocal()
    try:
        return db.get(Schedule, schedule_id).remaining_quota
    finally:
        db.close()


def _registration_count(schedule_id: int) -> int:
    db = SessionLocal()
    try:
        return (
            db.query(Registration)
            .filter(Registration.schedule_id == schedule_id)
            .count()
        )
    finally:
        db.close()


def _drug_stock(drug_id: int) -> int:
    db = SessionLocal()
    try:
        return db.get(Drug, drug_id).stock
    finally:
        db.close()


def _charge_count(prescription_id: int) -> int:
    db = SessionLocal()
    try:
        return (
            db.query(ChargeOrder)
            .filter(ChargeOrder.prescription_id == prescription_id)
            .count()
        )
    finally:
        db.close()


def _dispense_count(prescription_id: int) -> int:
    db = SessionLocal()
    try:
        return (
            db.query(DispenseRecord)
            .filter(DispenseRecord.prescription_id == prescription_id)
            .count()
        )
    finally:
        db.close()


def test_registration_normal_and_quota_exhausted(
    client, admin_headers, cashier_headers, doctor_id
):
    schedule = _create_schedule(
        client, admin_headers, doctor_id, max_quota=1
    )

    first = _register(
        client,
        cashier_headers,
        schedule["id"],
        name="号源患者一",
        phone="13800138001",
    )
    assert first.status_code == 201, first.text
    assert _schedule_remaining(schedule["id"]) == 0

    second = _register(
        client,
        cashier_headers,
        schedule["id"],
        name="号源患者二",
        phone="13800138002",
    )
    assert second.status_code == 400
    assert "no available quota" in second.json()["detail"]
    assert _schedule_remaining(schedule["id"]) == 0
    assert _registration_count(schedule["id"]) == 1


def test_charge_normal_and_duplicate_rejected(
    client, admin_headers, doctor_headers, cashier_headers, doctor_id
):
    drug_one = _create_drug(
        client, admin_headers, stock=10, unit_price="12.50"
    )
    drug_two = _create_drug(
        client, admin_headers, stock=10, unit_price="3.20"
    )
    prescription = _make_prescription(
        client,
        admin_headers,
        doctor_headers,
        doctor_id,
        items=[
            {"drug_id": drug_one["id"], "qty": 2},
            {"drug_id": drug_two["id"], "qty": 1},
        ],
        patient_name="收费测试患者",
    )

    first = _charge(
        client,
        cashier_headers,
        prescription["id"],
        total_amount=0.01,
        price=0.01,
    )
    assert first.status_code == 201, first.text
    assert first.json()["total_amount"] == pytest.approx(28.20)
    assert first.json()["prescription_paid"] is True
    assert _charge_count(prescription["id"]) == 1

    second = _charge(client, cashier_headers, prescription["id"])
    assert second.status_code == 409
    assert _charge_count(prescription["id"]) == 1


def test_dispense_normal_and_duplicate_rejected(
    client, admin_headers, doctor_headers, cashier_headers, pharmacist_headers, doctor_id
):
    drug = _create_drug(client, admin_headers, stock=10)
    prescription = _make_prescription(
        client,
        admin_headers,
        doctor_headers,
        doctor_id,
        items=[{"drug_id": drug["id"], "qty": 2}],
        patient_name="发药测试患者",
    )
    assert _charge(client, cashier_headers, prescription["id"]).status_code == 201

    first = _dispense(client, pharmacist_headers, prescription["id"])
    assert first.status_code == 201, first.text
    assert _drug_stock(drug["id"]) == 8
    assert _dispense_count(prescription["id"]) == 1

    second = _dispense(client, pharmacist_headers, prescription["id"])
    assert second.status_code == 409
    assert _drug_stock(drug["id"]) == 8
    assert _dispense_count(prescription["id"]) == 1


def test_dispense_insufficient_stock_rolls_back(
    client, admin_headers, doctor_headers, cashier_headers, pharmacist_headers, doctor_id
):
    drug = _create_drug(client, admin_headers, stock=1)
    prescription = _make_prescription(
        client,
        admin_headers,
        doctor_headers,
        doctor_id,
        items=[{"drug_id": drug["id"], "qty": 2}],
        patient_name="库存不足患者",
    )
    assert _charge(client, cashier_headers, prescription["id"]).status_code == 201

    response = _dispense(client, pharmacist_headers, prescription["id"])

    assert response.status_code == 400
    assert "insufficient stock" in response.json()["detail"]
    assert _drug_stock(drug["id"]) == 1
    assert _dispense_count(prescription["id"]) == 0


def test_unpaid_prescription_cannot_be_dispensed(
    client, admin_headers, doctor_headers, pharmacist_headers, doctor_id
):
    drug = _create_drug(client, admin_headers, stock=10)
    prescription = _make_prescription(
        client,
        admin_headers,
        doctor_headers,
        doctor_id,
        items=[{"drug_id": drug["id"], "qty": 2}],
        patient_name="未收费患者",
    )

    response = _dispense(client, pharmacist_headers, prescription["id"])

    assert response.status_code == 400
    assert "paid" in response.json()["detail"]
    assert _drug_stock(drug["id"]) == 10
    assert _dispense_count(prescription["id"]) == 0


def test_role_access_control(
    client,
    admin_headers,
    doctor_headers,
    cashier_headers,
    pharmacist_headers,
    doctor_id,
):
    schedule = _create_schedule(
        client, admin_headers, doctor_id, max_quota=2
    )
    registration_payload = {
        "patient_name": "权限患者",
        "phone": "13800138003",
        "schedule_id": schedule["id"],
    }

    assert (
        client.post(
            "/api/registrations",
            json=registration_payload,
            headers=doctor_headers,
        ).status_code
        == 403
    )
    assert (
        client.post(
            "/api/registrations",
            json=registration_payload,
            headers=pharmacist_headers,
        ).status_code
        == 403
    )
    assert (
        client.post(
            "/api/registrations",
            json=registration_payload,
            headers=admin_headers,
        ).status_code
        == 201
    )
    assert (
        client.post(
            "/api/registrations",
            json=registration_payload,
            headers=cashier_headers,
        ).status_code
        == 201
    )

    available_params = {
        "date": schedule["schedule_date"],
        "department": schedule["department"],
    }
    assert (
        client.get(
            "/api/schedules/available",
            params=available_params,
            headers=doctor_headers,
        ).status_code
        == 200
    )
    assert (
        client.get(
            "/api/schedules/available",
            params=available_params,
            headers=pharmacist_headers,
        ).status_code
        == 200
    )

    drug = _create_drug(client, admin_headers, stock=10)
    prescription = _make_prescription(
        client,
        admin_headers,
        doctor_headers,
        doctor_id,
        items=[{"drug_id": drug["id"], "qty": 1}],
        patient_name="越权处方患者",
    )

    assert (
        _charge(client, doctor_headers, prescription["id"]).status_code == 403
    )
    assert (
        _charge(client, pharmacist_headers, prescription["id"]).status_code
        == 403
    )
    assert _charge(client, cashier_headers, prescription["id"]).status_code == 201

    assert (
        _dispense(client, cashier_headers, prescription["id"]).status_code
        == 403
    )
    assert (
        _dispense(client, doctor_headers, prescription["id"]).status_code == 403
    )
    assert (
        _dispense(client, pharmacist_headers, prescription["id"]).status_code
        == 201
    )

    assert (
        client.post("/api/registrations", json=registration_payload).status_code
        == 401
    )
    assert (
        client.post(
            "/api/charge-orders", json={"prescription_id": prescription["id"]}
        ).status_code
        == 401
    )
    assert (
        client.post(
            "/api/dispenses", json={"prescription_id": prescription["id"]}
        ).status_code
        == 401
    )
