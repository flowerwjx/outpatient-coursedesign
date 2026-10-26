import itertools
import os
import sys
import tempfile
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

_TMP_DIR = tempfile.mkdtemp(prefix="his_charge_test_")
os.environ["DATABASE_URL"] = "sqlite:///" + (
    Path(_TMP_DIR) / "test_charge.db"
).as_posix()
os.environ.setdefault("JWT_SECRET", "test-only-secret")

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import pytest
from fastapi.testclient import TestClient

from app.database import Base, SessionLocal, engine
from app.main import app
from app.models.audit import AuditLog
from app.models.charge_order import ChargeOrder
from app.models.drug import Drug
from app.models.prescription import Prescription
from app.models.user import UserRole
from app.services.user_service import create_user

ACCOUNTS = [
    ("admin", "admin123", UserRole.ADMIN),
    ("doctor", "doc123", UserRole.DOCTOR),
    ("cashier", "cash123", UserRole.CASHIER),
    ("pharmacist", "pha123", UserRole.PHARMACIST),
]

DRUGS = [
    (1, "阿莫西林胶囊", "阿莫仙", "0.25g×24粒", "胶囊剂", "甲类", "12.50", 100),
    (2, "布洛芬缓释胶囊", "芬必得", "0.3g×20粒", "胶囊剂", "乙类", "3.20", 100),
]

_schedule_date_seq = itertools.count(1)


def _next_schedule_date() -> date:
    return date(2037, 1, 1) + timedelta(days=next(_schedule_date_seq))


@pytest.fixture(scope="module")
def client():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        for username, password, role in ACCOUNTS:
            create_user(db, username=username, password=password, role=role)

        for (
            drug_id,
            generic_name,
            trade_name,
            spec,
            dosage_form,
            insurance_type,
            unit_price,
            stock,
        ) in DRUGS:
            db.add(
                Drug(
                    id=drug_id,
                    generic_name=generic_name,
                    trade_name=trade_name,
                    spec=spec,
                    dosage_form=dosage_form,
                    insurance_type=insurance_type,
                    unit_price=Decimal(unit_price),
                    stock=stock,
                )
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


@pytest.fixture(scope="module")
def cashier_id(client, cashier_headers) -> int:
    return client.get("/api/me", headers=cashier_headers).json()["id"]


def _create_schedule(
    client: TestClient, admin_headers: dict, doctor_id: int
) -> dict:
    payload = {
        "department": "内科",
        "doctor_id": doctor_id,
        "schedule_date": _next_schedule_date().isoformat(),
        "max_quota": 2,
    }
    response = client.post("/api/schedules", json=payload, headers=admin_headers)
    assert response.status_code == 201, response.text
    return response.json()


def _register(
    client: TestClient, headers: dict, schedule_id: int, name: str
) -> dict:
    response = client.post(
        "/api/registrations",
        json={
            "patient_name": name,
            "phone": "13800138000",
            "schedule_id": schedule_id,
        },
        headers=headers,
    )
    assert response.status_code == 201, response.text
    return response.json()


def _make_prescription(
    client: TestClient,
    admin_headers: dict,
    doctor_headers: dict,
    doctor_id: int,
    items=None,
    patient_name: str = "收费患者",
) -> dict:
    schedule = _create_schedule(client, admin_headers, doctor_id)
    registration = _register(
        client, admin_headers, schedule["id"], patient_name
    )
    payload = {
        "registration_id": registration["id"],
        "icd10_code": "J06.9",
        "diagnosis_name": "急性上呼吸道感染",
        "items": items
        if items is not None
        else [
            {"drug_id": 1, "qty": 2},
            {"drug_id": 2, "qty": 1},
        ],
    }
    response = client.post(
        "/api/prescriptions", json=payload, headers=doctor_headers
    )
    assert response.status_code == 201, response.text
    return response.json()


def _charge(
    client: TestClient, headers: dict, prescription_id: int, **extra
):
    payload = {"prescription_id": prescription_id}
    payload.update(extra)
    return client.post(
        "/api/charge-orders", json=payload, headers=headers
    )


def _prescription_state(prescription_id: int):
    db = SessionLocal()
    try:
        prescription = db.get(Prescription, prescription_id)
        if prescription is None:
            return None
        return prescription.paid
    finally:
        db.close()


def _charge_order_count(prescription_id: int) -> int:
    db = SessionLocal()
    try:
        return (
            db.query(ChargeOrder)
            .filter(ChargeOrder.prescription_id == prescription_id)
            .count()
        )
    finally:
        db.close()


def _charge_order_total(prescription_id: int):
    db = SessionLocal()
    try:
        order = (
            db.query(ChargeOrder)
            .filter(ChargeOrder.prescription_id == prescription_id)
            .first()
        )
        return order.total_amount if order else None
    finally:
        db.close()


def _insert_manual_charge_order(
    prescription_id: int, cashier_id: int, total_amount: Decimal
) -> None:
    db = SessionLocal()
    try:
        db.add(
            ChargeOrder(
                prescription_id=prescription_id,
                cashier_id=cashier_id,
                total_amount=total_amount,
            )
        )
        db.commit()
    finally:
        db.close()


def test_cashier_can_charge_unpaid_prescription(
    client, admin_headers, doctor_headers, cashier_headers, doctor_id, cashier_id
):
    prescription = _make_prescription(
        client,
        admin_headers,
        doctor_headers,
        doctor_id,
        patient_name="正常收费患者",
    )

    response = _charge(
        client, cashier_headers, prescription["id"]
    )

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["prescription_id"] == prescription["id"]
    assert body["total_amount"] == pytest.approx(28.20)
    assert body["cashier_id"] == cashier_id
    assert body["cashier_username"] == "cashier"
    assert body["patient_name"] == "正常收费患者"
    assert body["department"] == "内科"
    assert body["icd10_code"] == "J06.9"
    assert body["diagnosis_name"] == "急性上呼吸道感染"
    assert body["prescription_paid"] is True
    assert body["charged_at"]

    assert _prescription_state(prescription["id"]) is True
    assert _charge_order_count(prescription["id"]) == 1
    assert _charge_order_total(prescription["id"]) == Decimal("28.20")

    db = SessionLocal()
    try:
        log = (
            db.query(AuditLog)
            .filter(AuditLog.path == "/api/charge-orders")
            .order_by(AuditLog.id.desc())
            .first()
        )
    finally:
        db.close()

    assert log is not None
    assert log.operator_id == cashier_id
    assert log.method == "POST"
    assert log.status_code == 201


def test_client_supplied_price_is_ignored(
    client, admin_headers, doctor_headers, cashier_headers, doctor_id
):
    prescription = _make_prescription(
        client,
        admin_headers,
        doctor_headers,
        doctor_id,
        patient_name="价格篡改患者",
    )

    response = _charge(
        client,
        cashier_headers,
        prescription["id"],
        total_amount=0.01,
        price=0.01,
        unit_price=0.01,
    )

    assert response.status_code == 201, response.text
    assert response.json()["total_amount"] == pytest.approx(28.20)
    assert _charge_order_total(prescription["id"]) == Decimal("28.20")


def test_already_paid_prescription_returns_409(
    client, admin_headers, doctor_headers, cashier_headers, doctor_id
):
    prescription = _make_prescription(
        client,
        admin_headers,
        doctor_headers,
        doctor_id,
        patient_name="重复收费患者",
    )

    first = _charge(client, cashier_headers, prescription["id"])
    second = _charge(client, cashier_headers, prescription["id"])

    assert first.status_code == 201
    assert second.status_code == 409
    assert "already paid" in second.json()["detail"]
    assert _charge_order_count(prescription["id"]) == 1
    assert _prescription_state(prescription["id"]) is True


def test_only_cashier_can_charge(
    client,
    admin_headers,
    doctor_headers,
    cashier_headers,
    pharmacist_headers,
    doctor_id,
):
    prescription = _make_prescription(
        client,
        admin_headers,
        doctor_headers,
        doctor_id,
        patient_name="权限收费患者",
    )

    assert (
        _charge(client, admin_headers, prescription["id"]).status_code == 403
    )
    assert (
        _charge(client, doctor_headers, prescription["id"]).status_code == 403
    )
    assert (
        _charge(client, pharmacist_headers, prescription["id"]).status_code
        == 403
    )
    assert (
        client.post(
            "/api/charge-orders",
            json={"prescription_id": prescription["id"]},
        ).status_code
        == 401
    )

    assert _prescription_state(prescription["id"]) is False
    assert _charge_order_count(prescription["id"]) == 0


def test_charge_missing_prescription_returns_404(
    client, cashier_headers
):
    response = _charge(client, cashier_headers, 999999999)
    assert response.status_code == 404


def test_charge_fails_when_drug_missing_from_archive(
    client, admin_headers, doctor_headers, cashier_headers, doctor_id
):
    prescription = _make_prescription(
        client,
        admin_headers,
        doctor_headers,
        doctor_id,
        items=[{"drug_id": 999, "qty": 1}],
        patient_name="缺药患者",
    )

    response = _charge(client, cashier_headers, prescription["id"])

    assert response.status_code == 400
    assert "not found in drug archive" in response.json()["detail"]
    assert _prescription_state(prescription["id"]) is False
    assert _charge_order_count(prescription["id"]) == 0


def test_charge_rolls_back_when_charge_order_conflicts(
    client,
    admin_headers,
    doctor_headers,
    cashier_headers,
    doctor_id,
    cashier_id,
):
    prescription = _make_prescription(
        client,
        admin_headers,
        doctor_headers,
        doctor_id,
        patient_name="事务回滚患者",
    )
    _insert_manual_charge_order(
        prescription["id"], cashier_id, Decimal("1.00")
    )

    response = _charge(client, cashier_headers, prescription["id"])

    assert response.status_code == 409
    assert _prescription_state(prescription["id"]) is False
    assert _charge_order_count(prescription["id"]) == 1


def test_cashier_can_list_unpaid_prescriptions(
    client,
    admin_headers,
    doctor_headers,
    cashier_headers,
    pharmacist_headers,
    doctor_id,
):
    unpaid = _make_prescription(
        client,
        admin_headers,
        doctor_headers,
        doctor_id,
        patient_name="待收费患者A",
    )
    charged = _make_prescription(
        client,
        admin_headers,
        doctor_headers,
        doctor_id,
        patient_name="已收费患者B",
    )
    assert _charge(client, cashier_headers, charged["id"]).status_code == 201

    response = client.get("/api/prescriptions", headers=cashier_headers)

    assert response.status_code == 200
    records = response.json()
    ids = [item["id"] for item in records]
    assert unpaid["id"] in ids
    assert charged["id"] not in ids

    unpaid_record = next(
        item for item in records if item["id"] == unpaid["id"]
    )
    assert unpaid_record["patient_name"] == "待收费患者A"
    assert unpaid_record["patient_phone"] == "13800138000"
    assert len(unpaid_record["items"]) == 2

    paid_response = client.get(
        "/api/prescriptions",
        params={"paid": "true"},
        headers=cashier_headers,
    )
    assert paid_response.status_code == 200
    assert charged["id"] in [item["id"] for item in paid_response.json()]

    assert (
        client.get("/api/prescriptions", headers=doctor_headers).status_code
        == 403
    )
    assert (
        client.get("/api/prescriptions", headers=pharmacist_headers).status_code
        == 200
    )
    assert client.get("/api/prescriptions").status_code == 401


def test_charge_preview_returns_backend_prices(
    client, admin_headers, doctor_headers, cashier_headers, doctor_id
):
    prescription = _make_prescription(
        client,
        admin_headers,
        doctor_headers,
        doctor_id,
        patient_name="预览收费患者",
    )

    response = client.get(
        f"/api/prescriptions/{prescription['id']}/charge-preview",
        headers=cashier_headers,
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["prescription_id"] == prescription["id"]
    assert body["patient_name"] == "预览收费患者"
    assert body["patient_phone"] == "13800138000"
    assert body["total_amount"] == pytest.approx(28.20)
    prices = {
        item["drug_id"]: (item["unit_price"], item["line_total"])
        for item in body["items"]
    }
    assert prices[1] == (pytest.approx(12.50), pytest.approx(25.00))
    assert prices[2] == (pytest.approx(3.20), pytest.approx(3.20))

    assert (
        client.get(
            f"/api/prescriptions/{prescription['id']}/charge-preview",
            headers=doctor_headers,
        ).status_code
        == 403
    )

    assert _charge(client, cashier_headers, prescription["id"]).status_code == 201
    assert (
        client.get(
            f"/api/prescriptions/{prescription['id']}/charge-preview",
            headers=cashier_headers,
        ).status_code
        == 409
    )


def test_cashier_can_list_charge_orders(
    client, admin_headers, doctor_headers, cashier_headers, doctor_id
):
    prescription = _make_prescription(
        client,
        admin_headers,
        doctor_headers,
        doctor_id,
        patient_name="收费记录患者",
    )
    charge = _charge(client, cashier_headers, prescription["id"])
    assert charge.status_code == 201
    order = charge.json()

    response = client.get("/api/charge-orders", headers=cashier_headers)

    assert response.status_code == 200
    records = response.json()
    record = next(item for item in records if item["id"] == order["id"])
    assert record["prescription_id"] == prescription["id"]
    assert record["patient_name"] == "收费记录患者"
    assert record["total_amount"] == pytest.approx(28.20)
    assert record["cashier_username"] == "cashier"

    assert (
        client.get("/api/charge-orders", headers=admin_headers).status_code
        == 403
    )
    assert (
        client.get("/api/charge-orders", headers=doctor_headers).status_code
        == 403
    )
    assert client.get("/api/charge-orders").status_code == 401
