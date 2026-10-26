import itertools
import os
import sys
import tempfile
from datetime import date, timedelta
from pathlib import Path

_TMP_DIR = tempfile.mkdtemp(prefix="his_registration_test_")
os.environ["DATABASE_URL"] = "sqlite:///" + (Path(_TMP_DIR) / "test_registration.db").as_posix()
os.environ.setdefault("JWT_SECRET", "test-only-secret")

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import pytest
from fastapi.testclient import TestClient

from app.database import Base, SessionLocal, engine
from app.main import app
from app.models.audit import AuditLog
from app.models.registration import Registration, RegistrationStatus
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


def _next_schedule_date() -> date:
    return date(2035, 1, 1) + timedelta(days=next(_schedule_date_seq))


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


@pytest.fixture(scope="module")
def cashier_id(client, cashier_headers) -> int:
    return client.get("/api/me", headers=cashier_headers).json()["id"]


def _user_id(client: TestClient, headers: dict) -> int:
    return client.get("/api/me", headers=headers).json()["id"]


def _create_schedule(
    client: TestClient,
    admin_headers: dict,
    doctor_id: int,
    **overrides,
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


def _schedule_state(schedule_id: int):
    db = SessionLocal()
    try:
        schedule = db.get(Schedule, schedule_id)
        if schedule is None:
            return None
        return schedule.max_quota, schedule.remaining_quota
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


def _register(
    client: TestClient,
    headers: dict,
    schedule_id: int,
    name: str = "张三",
    phone: str = "13800138000",
):
    return client.post(
        "/api/registrations",
        json={"patient_name": name, "phone": phone, "schedule_id": schedule_id},
        headers=headers,
    )


def test_admin_can_create_schedule_with_initialized_quota(
    client, admin_headers, doctor_id
):
    schedule = _create_schedule(
        client, admin_headers, doctor_id, max_quota=5, department="内科"
    )

    assert schedule["id"] > 0
    assert schedule["department"] == "内科"
    assert schedule["doctor_id"] == doctor_id
    assert schedule["doctor_username"] == "doctor"
    assert schedule["max_quota"] == 5
    assert schedule["remaining_quota"] == 5
    assert schedule["used_quota"] == 0


def test_only_admin_can_create_schedule(client, admin_headers, doctor_headers, doctor_id):
    payload = {
        "department": "外科",
        "doctor_id": doctor_id,
        "schedule_date": _next_schedule_date().isoformat(),
        "max_quota": 2,
    }

    assert (
        client.post("/api/schedules", json=payload, headers=doctor_headers).status_code
        == 403
    )
    assert client.post("/api/schedules", json=payload).status_code == 401


def test_non_admin_cannot_update_or_delete_schedule(
    client, admin_headers, doctor_headers, doctor_id
):
    schedule = _create_schedule(client, admin_headers, doctor_id)

    update_response = client.put(
        f"/api/schedules/{schedule['id']}",
        json={"max_quota": 10},
        headers=doctor_headers,
    )
    delete_response = client.delete(
        f"/api/schedules/{schedule['id']}", headers=doctor_headers
    )

    assert update_response.status_code == 403
    assert delete_response.status_code == 403


def test_create_schedule_rejects_non_doctor_account(
    client, admin_headers, cashier_headers
):
    cashier_id = _user_id(client, cashier_headers)

    response = client.post(
        "/api/schedules",
        json={
            "department": "内科",
            "doctor_id": cashier_id,
            "schedule_date": _next_schedule_date().isoformat(),
            "max_quota": 2,
        },
        headers=admin_headers,
    )

    assert response.status_code == 400
    assert "not a valid doctor" in response.json()["detail"]


def test_duplicate_schedule_returns_409(client, admin_headers, doctor_id):
    payload = {
        "department": "内科",
        "doctor_id": doctor_id,
        "schedule_date": _next_schedule_date().isoformat(),
        "max_quota": 2,
    }

    first = client.post("/api/schedules", json=payload, headers=admin_headers)
    second = client.post("/api/schedules", json=payload, headers=admin_headers)

    assert first.status_code == 201
    assert second.status_code == 409


def test_available_schedules_filter_by_date_and_department(
    client, admin_headers, doctor_headers, cashier_headers, doctor_id
):
    target_date = date(2040, 1, 1)
    internal = _create_schedule(
        client,
        admin_headers,
        doctor_id,
        department="内科",
        schedule_date=target_date.isoformat(),
        max_quota=1,
    )
    surgery = _create_schedule(
        client,
        admin_headers,
        doctor_id,
        department="外科",
        schedule_date=target_date.isoformat(),
        max_quota=2,
    )
    _create_schedule(
        client,
        admin_headers,
        doctor_id,
        department="内科",
        schedule_date=(target_date + timedelta(days=1)).isoformat(),
        max_quota=2,
    )

    internal_response = client.get(
        "/api/schedules/available",
        params={"date": target_date.isoformat(), "department": "内科"},
        headers=doctor_headers,
    )
    surgery_response = client.get(
        "/api/schedules/available",
        params={"date": target_date.isoformat(), "department": "外科"},
        headers=doctor_headers,
    )
    other_response = client.get(
        "/api/schedules/available",
        params={"date": target_date.isoformat(), "department": "儿科"},
        headers=doctor_headers,
    )

    assert [item["id"] for item in internal_response.json()] == [internal["id"]]
    assert [item["id"] for item in surgery_response.json()] == [surgery["id"]]
    assert other_response.json() == []

    assert _register(client, cashier_headers, internal["id"]).status_code == 201
    exhausted_response = client.get(
        "/api/schedules/available",
        params={"date": target_date.isoformat(), "department": "内科"},
        headers=doctor_headers,
    )
    assert exhausted_response.json() == []


def test_available_schedules_require_login(client):
    response = client.get(
        "/api/schedules/available",
        params={"date": "2040-01-01", "department": "内科"},
    )
    assert response.status_code == 401


def test_admin_can_list_schedules(client, admin_headers, doctor_headers, doctor_id):
    target_date = _next_schedule_date()
    schedule = _create_schedule(
        client,
        admin_headers,
        doctor_id,
        department="眼科",
        schedule_date=target_date.isoformat(),
    )

    response = client.get(
        "/api/schedules",
        params={"date": target_date.isoformat(), "department": "眼科"},
        headers=admin_headers,
    )

    assert response.status_code == 200
    assert [item["id"] for item in response.json()] == [schedule["id"]]
    assert (
        client.get("/api/schedules", headers=doctor_headers).status_code == 403
    )


def test_registration_deducts_quota_and_writes_audit_log(
    client, admin_headers, cashier_headers, cashier_id, doctor_id
):
    schedule = _create_schedule(client, admin_headers, doctor_id, max_quota=2)

    response = _register(
        client, cashier_headers, schedule["id"], name="李四", phone="13900139000"
    )

    assert response.status_code == 201
    body = response.json()
    assert body["patient_name"] == "李四"
    assert body["phone"] == "13900139000"
    assert body["schedule_id"] == schedule["id"]
    assert body["status"] == RegistrationStatus.REGISTERED.value
    assert _schedule_state(schedule["id"]) == (2, 1)
    assert _registration_count(schedule["id"]) == 1

    db = SessionLocal()
    try:
        log = (
            db.query(AuditLog)
            .filter(AuditLog.path == "/api/registrations")
            .order_by(AuditLog.id.desc())
            .first()
        )
    finally:
        db.close()

    assert log is not None
    assert log.operator_id == cashier_id
    assert log.method == "POST"
    assert log.status_code == 201


def test_registration_when_quota_exhausted_returns_400_and_rolls_back(
    client, admin_headers, cashier_headers, doctor_id
):
    schedule = _create_schedule(client, admin_headers, doctor_id, max_quota=1)

    assert _register(client, cashier_headers, schedule["id"]).status_code == 201
    response = _register(
        client,
        cashier_headers,
        schedule["id"],
        name="王五",
        phone="13700137000",
    )

    assert response.status_code == 400
    assert "no available quota" in response.json()["detail"]
    assert _schedule_state(schedule["id"]) == (1, 0)
    assert _registration_count(schedule["id"]) == 1


def test_registration_for_missing_schedule_returns_404(client, cashier_headers):
    response = _register(client, cashier_headers, 999999999)
    assert response.status_code == 404


def test_registration_requires_login(client, admin_headers, doctor_id):
    schedule = _create_schedule(client, admin_headers, doctor_id)

    response = client.post(
        "/api/registrations",
        json={
            "patient_name": "赵六",
            "phone": "13600136000",
            "schedule_id": schedule["id"],
        },
    )

    assert response.status_code == 401


def test_registration_permissions_are_admin_and_cashier_only(
    client,
    admin_headers,
    doctor_headers,
    cashier_headers,
    pharmacist_headers,
    doctor_id,
):
    schedule = _create_schedule(client, admin_headers, doctor_id, max_quota=3)
    payload = {
        "patient_name": "权限验证患者",
        "phone": "13600136000",
        "schedule_id": schedule["id"],
    }

    assert (
        client.post(
            "/api/registrations", json=payload, headers=doctor_headers
        ).status_code
        == 403
    )
    assert (
        client.post(
            "/api/registrations", json=payload, headers=pharmacist_headers
        ).status_code
        == 403
    )
    assert (
        client.post(
            "/api/registrations", json=payload, headers=admin_headers
        ).status_code
        == 201
    )
    assert (
        client.post(
            "/api/registrations", json=payload, headers=cashier_headers
        ).status_code
        == 201
    )

    assert _schedule_state(schedule["id"]) == (3, 1)
    assert _registration_count(schedule["id"]) == 2

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


def test_update_schedule_recalculates_remaining_and_blocks_used_quota(
    client, admin_headers, cashier_headers, doctor_id
):
    schedule = _create_schedule(client, admin_headers, doctor_id, max_quota=3)
    assert _register(client, cashier_headers, schedule["id"]).status_code == 201
    assert (
        _register(
            client,
            cashier_headers,
            schedule["id"],
            name="孙七",
            phone="13500135000",
        ).status_code
        == 201
    )

    response = client.put(
        f"/api/schedules/{schedule['id']}",
        json={"max_quota": 2},
        headers=admin_headers,
    )
    assert response.status_code == 200
    assert response.json()["max_quota"] == 2
    assert response.json()["remaining_quota"] == 0
    assert response.json()["used_quota"] == 2

    invalid_response = client.put(
        f"/api/schedules/{schedule['id']}",
        json={"max_quota": 1},
        headers=admin_headers,
    )
    assert invalid_response.status_code == 400
    assert _schedule_state(schedule["id"]) == (2, 0)

    expanded_response = client.put(
        f"/api/schedules/{schedule['id']}",
        json={"max_quota": 5, "department": "内科专家门诊"},
        headers=admin_headers,
    )
    assert expanded_response.status_code == 200
    assert expanded_response.json()["department"] == "内科专家门诊"
    assert expanded_response.json()["remaining_quota"] == 3


def test_update_schedule_with_empty_payload_returns_422(
    client, admin_headers, doctor_id
):
    schedule = _create_schedule(client, admin_headers, doctor_id)

    response = client.put(
        f"/api/schedules/{schedule['id']}", json={}, headers=admin_headers
    )

    assert response.status_code == 422


def test_delete_schedule_blocked_when_registrations_exist(
    client, admin_headers, cashier_headers, doctor_id
):
    schedule = _create_schedule(client, admin_headers, doctor_id)
    assert _register(client, cashier_headers, schedule["id"]).status_code == 201

    response = client.delete(
        f"/api/schedules/{schedule['id']}", headers=admin_headers
    )

    assert response.status_code == 409
    assert _schedule_state(schedule["id"]) is not None


def test_delete_schedule_without_registrations(client, admin_headers, doctor_id):
    schedule = _create_schedule(client, admin_headers, doctor_id)

    response = client.delete(
        f"/api/schedules/{schedule['id']}", headers=admin_headers
    )

    assert response.status_code == 204
    assert _schedule_state(schedule["id"]) is None

def test_list_registrations_returns_schedule_info(
    client, admin_headers, doctor_headers, cashier_headers, doctor_id
):
    schedule = _create_schedule(client, admin_headers, doctor_id, max_quota=2)
    created = _register(
        client, cashier_headers, schedule["id"], name="周八", phone="13400134000"
    ).json()

    response = client.get(
        "/api/registrations",
        params={"schedule_id": schedule["id"]},
        headers=doctor_headers,
    )

    assert response.status_code == 200
    records = response.json()
    assert [item["id"] for item in records] == [created["id"]]
    assert records[0]["patient_name"] == "周八"
    assert records[0]["department"] == schedule["department"]
    assert records[0]["schedule_date"] == schedule["schedule_date"]
    assert records[0]["doctor_username"] == "doctor"

    assert (
        client.get(
            "/api/registrations",
            params={"schedule_id": schedule["id"]},
        ).status_code
        == 401
    )


def test_admin_can_list_doctors(client, admin_headers, doctor_headers, doctor_id):
    response = client.get("/api/doctors", headers=admin_headers)

    assert response.status_code == 200
    doctors = response.json()
    assert {"id": doctor_id, "username": "doctor", "role": "doctor"} in doctors

    assert client.get("/api/doctors", headers=doctor_headers).status_code == 403
    assert client.get("/api/doctors").status_code == 401
