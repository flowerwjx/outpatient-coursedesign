import itertools
import os
import sys
import tempfile
from datetime import date, timedelta
from pathlib import Path

_TMP_DIR = tempfile.mkdtemp(prefix="his_prescription_test_")
os.environ["DATABASE_URL"] = "sqlite:///" + (
    Path(_TMP_DIR) / "test_prescription.db"
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
from app.models.prescription import Prescription, PrescriptionItem
from app.models.registration import Registration, RegistrationStatus
from app.models.user import UserRole
from app.services.user_service import create_user

ACCOUNTS = [
    ("admin", "admin123", UserRole.ADMIN),
    ("doctor", "doc123", UserRole.DOCTOR),
    ("doctor2", "doc456", UserRole.DOCTOR),
    ("cashier", "cash123", UserRole.CASHIER),
    ("pharmacist", "pha123", UserRole.PHARMACIST),
]

_schedule_date_seq = itertools.count(1)


def _next_schedule_date() -> date:
    return date(2036, 1, 1) + timedelta(days=next(_schedule_date_seq))


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
def doctor2_headers(client):
    return _headers(_login(client, "doctor2", "doc456"))


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
def doctor2_id(client, doctor2_headers) -> int:
    return client.get("/api/me", headers=doctor2_headers).json()["id"]


def _create_schedule(
    client: TestClient, admin_headers: dict, doctor_id: int, **overrides
) -> dict:
    payload = {
        "department": "内科",
        "doctor_id": doctor_id,
        "schedule_date": _next_schedule_date().isoformat(),
        "max_quota": 2,
    }
    payload.update(overrides)
    response = client.post("/api/schedules", json=payload, headers=admin_headers)
    assert response.status_code == 201, response.text
    return response.json()


def _register(
    client: TestClient,
    headers: dict,
    schedule_id: int,
    name: str,
    phone: str,
):
    return client.post(
        "/api/registrations",
        json={"patient_name": name, "phone": phone, "schedule_id": schedule_id},
        headers=headers,
    )


def _make_registration(
    client: TestClient,
    admin_headers: dict,
    doctor_id: int,
    name: str = "张三",
    phone: str = "13800138000",
) -> tuple[dict, dict]:
    schedule = _create_schedule(
        client, admin_headers, doctor_id, department="内科"
    )
    response = _register(
        client, admin_headers, schedule["id"], name=name, phone=phone
    )
    assert response.status_code == 201, response.text
    return schedule, response.json()


def _prescription_payload(registration_id: int, **overrides) -> dict:
    payload = {
        "registration_id": registration_id,
        "icd10_code": "J06.9",
        "diagnosis_name": "急性上呼吸道感染",
        "items": [
            {"drug_id": 1, "qty": 2},
            {"drug_id": 2, "qty": 1},
        ],
    }
    payload.update(overrides)
    return payload


def _create_prescription(client: TestClient, headers: dict, payload: dict):
    return client.post("/api/prescriptions", json=payload, headers=headers)


def _set_registration_status(
    registration_id: int, status: RegistrationStatus
) -> None:
    db = SessionLocal()
    try:
        registration = db.get(Registration, registration_id)
        registration.status = status
        db.commit()
    finally:
        db.close()


def _prescription_items(registration_id: int):
    db = SessionLocal()
    try:
        prescription = (
            db.query(Prescription)
            .filter(Prescription.registration_id == registration_id)
            .first()
        )
        if prescription is None:
            return None
        return [(item.drug_id, item.qty) for item in prescription.items]
    finally:
        db.close()


def _pending_ids(client: TestClient, headers: dict) -> list[int]:
    response = client.get(
        "/api/doctor/pending-registrations", headers=headers
    )
    assert response.status_code == 200, response.text
    return [item["id"] for item in response.json()]


def test_doctor_pending_list_only_contains_own_registrations(
    client, admin_headers, doctor_headers, doctor2_headers, doctor_id, doctor2_id
):
    _, own_registration = _make_registration(
        client,
        admin_headers,
        doctor_id,
        name="待接诊患者",
        phone="13800138001",
    )
    _, other_registration = _make_registration(
        client,
        admin_headers,
        doctor2_id,
        name="其他医生患者",
        phone="13800138002",
    )

    response = client.get(
        "/api/doctor/pending-registrations", headers=doctor_headers
    )

    assert response.status_code == 200
    records = response.json()
    ids = [item["id"] for item in records]
    assert own_registration["id"] in ids
    assert other_registration["id"] not in ids

    own_record = next(
        item for item in records if item["id"] == own_registration["id"]
    )
    assert own_record["patient_name"] == "待接诊患者"
    assert own_record["department"] == "内科"
    assert own_record["doctor_username"] == "doctor"

    other_ids = _pending_ids(client, doctor2_headers)
    assert other_registration["id"] in other_ids
    assert own_registration["id"] not in other_ids


def test_pending_list_requires_doctor_role(
    client, admin_headers, cashier_headers
):
    assert (
        client.get(
            "/api/doctor/pending-registrations", headers=admin_headers
        ).status_code
        == 403
    )
    assert (
        client.get(
            "/api/doctor/pending-registrations", headers=cashier_headers
        ).status_code
        == 403
    )
    assert (
        client.get("/api/doctor/pending-registrations").status_code == 401
    )


def test_doctor_can_create_prescription_with_batch_items(
    client, admin_headers, doctor_headers, doctor_id
):
    _, registration = _make_registration(
        client,
        admin_headers,
        doctor_id,
        name="处方患者",
        phone="13800138003",
    )

    response = _create_prescription(
        client,
        doctor_headers,
        _prescription_payload(
            registration["id"],
            icd10_code="j06.9",
            diagnosis_name="  急性上呼吸道感染  ",
        ),
    )

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["registration_id"] == registration["id"]
    assert body["doctor_id"] == doctor_id
    assert body["icd10_code"] == "J06.9"
    assert body["diagnosis_name"] == "急性上呼吸道感染"
    assert body["paid"] is False
    assert body["patient_name"] == "处方患者"
    assert body["department"] == "内科"
    assert body["doctor_username"] == "doctor"
    assert {(item["drug_id"], item["qty"]) for item in body["items"]} == {
        (1, 2),
        (2, 1),
    }
    assert _prescription_items(registration["id"]) == [(1, 2), (2, 1)]

    db = SessionLocal()
    try:
        prescription = (
            db.query(Prescription)
            .filter(Prescription.registration_id == registration["id"])
            .first()
        )
        item_count = (
            db.query(PrescriptionItem)
            .filter(PrescriptionItem.prescription_id == prescription.id)
            .count()
        )
        log = (
            db.query(AuditLog)
            .filter(AuditLog.path == "/api/prescriptions")
            .order_by(AuditLog.id.desc())
            .first()
        )
    finally:
        db.close()

    assert prescription is not None
    assert prescription.paid is False
    assert item_count == 2
    assert log is not None
    assert log.operator_id == doctor_id
    assert log.method == "POST"
    assert log.status_code == 201


def test_prescription_removes_registration_from_pending_list(
    client, admin_headers, doctor_headers, doctor_id
):
    _, registration = _make_registration(
        client,
        admin_headers,
        doctor_id,
        name="复诊患者",
        phone="13800138004",
    )
    assert registration["id"] in _pending_ids(client, doctor_headers)

    response = _create_prescription(
        client, doctor_headers, _prescription_payload(registration["id"])
    )
    assert response.status_code == 201

    assert registration["id"] not in _pending_ids(client, doctor_headers)


def test_create_prescription_requires_doctor_role(
    client,
    admin_headers,
    cashier_headers,
    pharmacist_headers,
    doctor2_id,
):
    _, registration = _make_registration(
        client,
        admin_headers,
        doctor2_id,
        name="权限测试患者",
        phone="13800138005",
    )
    payload = _prescription_payload(registration["id"])

    assert _create_prescription(client, admin_headers, payload).status_code == 403
    assert (
        _create_prescription(client, cashier_headers, payload).status_code == 403
    )
    assert (
        _create_prescription(client, pharmacist_headers, payload).status_code
        == 403
    )
    assert (
        client.post("/api/prescriptions", json=payload).status_code == 401
    )


def test_doctor_cannot_prescribe_other_doctors_registration(
    client, admin_headers, doctor_headers, doctor2_id
):
    _, registration = _make_registration(
        client,
        admin_headers,
        doctor2_id,
        name="跨医生患者",
        phone="13800138006",
    )

    response = _create_prescription(
        client, doctor_headers, _prescription_payload(registration["id"])
    )

    assert response.status_code == 403
    assert "does not belong" in response.json()["detail"]


def test_create_prescription_for_missing_registration_returns_404(
    client, doctor_headers
):
    response = _create_prescription(
        client, doctor_headers, _prescription_payload(999999999)
    )
    assert response.status_code == 404


def test_duplicate_prescription_returns_409(
    client, admin_headers, doctor_headers, doctor_id
):
    _, registration = _make_registration(
        client,
        admin_headers,
        doctor_id,
        name="重复处方患者",
        phone="13800138007",
    )
    payload = _prescription_payload(registration["id"])

    assert _create_prescription(client, doctor_headers, payload).status_code == 201
    assert _create_prescription(client, doctor_headers, payload).status_code == 409


def test_cancelled_registration_cannot_get_prescription(
    client, admin_headers, doctor_headers, doctor_id
):
    _, registration = _make_registration(
        client,
        admin_headers,
        doctor_id,
        name="取消挂号患者",
        phone="13800138008",
    )
    _set_registration_status(
        registration["id"], RegistrationStatus.CANCELLED
    )

    response = _create_prescription(
        client, doctor_headers, _prescription_payload(registration["id"])
    )

    assert response.status_code == 400
    assert registration["id"] not in _pending_ids(client, doctor_headers)


@pytest.mark.parametrize(
    "overrides",
    [
        {"icd10_code": "abc"},
        {"diagnosis_name": "   "},
        {"items": []},
        {"items": [{"drug_id": 1, "qty": 0}]},
        {"items": [{"drug_id": 1, "qty": 1}, {"drug_id": 1, "qty": 2}]},
        {"doctor_id": 1},
        {"paid": True},
    ],
)
def test_prescription_validation_rejects_invalid_payload(
    client, admin_headers, doctor_headers, doctor_id, overrides
):
    _, registration = _make_registration(
        client,
        admin_headers,
        doctor_id,
        name="校验患者",
        phone="13800138009",
    )

    response = _create_prescription(
        client,
        doctor_headers,
        _prescription_payload(registration["id"], **overrides),
    )

    assert response.status_code == 422
