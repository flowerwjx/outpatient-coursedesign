import json
import os
import sys
import tempfile
from datetime import date, datetime
from pathlib import Path

_TMP_DIR = tempfile.mkdtemp(prefix="his_audit_test_")
os.environ["DATABASE_URL"] = "sqlite:///" + (
    Path(_TMP_DIR) / "test_audit.db"
).as_posix()
os.environ.setdefault("JWT_SECRET", "test-only-secret")

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import inspect

from app.database import Base, SessionLocal, engine
from app.main import app
from app.models.audit import AuditLog
from app.models.user import UserRole
from app.services.user_service import create_user


@pytest.fixture(scope="module")
def client():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        create_user(db, username="admin", password="admin123", role=UserRole.ADMIN)
    finally:
        db.close()

    with TestClient(app) as test_client:
        yield test_client

    Base.metadata.drop_all(bind=engine)


def _login(client: TestClient) -> str:
    response = client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "admin123"},
    )
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="module")
def admin_headers(client):
    return _headers(_login(client))


@pytest.fixture(scope="module")
def admin_id(client, admin_headers) -> int:
    return client.get("/api/me", headers=admin_headers).json()["id"]


def _audit_count() -> int:
    db = SessionLocal()
    try:
        return db.query(AuditLog).count()
    finally:
        db.close()


def _latest_audit(path: str, method: str):
    db = SessionLocal()
    try:
        return (
            db.query(AuditLog)
            .filter(AuditLog.path == path, AuditLog.method == method)
            .order_by(AuditLog.id.desc())
            .first()
        )
    finally:
        db.close()


def test_audit_log_uses_required_database_columns(client):
    columns = {
        column["name"]
        for column in inspect(engine).get_columns("audit_logs")
    }

    assert {
        "operator_user_id",
        "operate_time",
        "request_path",
        "method",
        "payload",
    }.issubset(columns)


def test_login_is_audited_and_password_is_redacted(client):
    response = client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "admin123"},
    )
    assert response.status_code == 200

    db = SessionLocal()
    try:
        log = (
            db.query(AuditLog)
            .filter(AuditLog.path == "/api/auth/login")
            .order_by(AuditLog.id.desc())
            .first()
        )
    finally:
        db.close()

    assert log is not None
    assert log.method == "POST"
    assert log.status_code == 200
    assert log.operator_id is not None
    assert log.payload is not None
    assert "admin123" not in log.payload
    assert "***" in log.payload


def test_get_is_not_audited(client, admin_headers):
    before_get = _audit_count()
    assert client.get("/api/me", headers=admin_headers).status_code == 200
    assert _audit_count() == before_get


def test_post_put_delete_are_audited(client, admin_headers, admin_id):
    db = SessionLocal()
    try:
        from app.models.user import User

        doctor = User(
            username="audit_doctor",
            password_hash="not-used",
            role=UserRole.DOCTOR,
        )
        db.add(doctor)
        db.commit()
        doctor_id = doctor.id
    finally:
        db.close()

    payload = {
        "department": "内科",
        "doctor_id": doctor_id,
        "schedule_date": date(2039, 2, 1).isoformat(),
        "max_quota": 2,
    }
    create_response = client.post(
        "/api/schedules", json=payload, headers=admin_headers
    )
    assert create_response.status_code == 201, create_response.text
    schedule_id = create_response.json()["id"]

    update_response = client.put(
        f"/api/schedules/{schedule_id}",
        json={"max_quota": 5},
        headers=admin_headers,
    )
    assert update_response.status_code == 200

    delete_response = client.delete(
        f"/api/schedules/{schedule_id}", headers=admin_headers
    )
    assert delete_response.status_code == 204

    create_log = _latest_audit("/api/schedules", "POST")
    update_log = _latest_audit(f"/api/schedules/{schedule_id}", "PUT")
    delete_log = _latest_audit(f"/api/schedules/{schedule_id}", "DELETE")

    assert create_log is not None
    assert create_log.operator_id == admin_id
    assert create_log.status_code == 201
    assert "内科" in (create_log.payload or "")
    assert create_log.created_at is not None

    assert update_log is not None
    assert update_log.operator_id == admin_id
    assert update_log.status_code == 200
    assert json.loads(update_log.payload)["max_quota"] == 5

    assert delete_log is not None
    assert delete_log.operator_id == admin_id
    assert delete_log.status_code == 204


def test_admin_can_query_and_filter_audit_logs(
    client, admin_headers, admin_id
):
    db = SessionLocal()
    try:
        doctor = create_user(
            db, username="audit_query_doctor", password="doc123", role=UserRole.DOCTOR
        )
        doctor_id = doctor.id
        db.add(
            AuditLog(
                operator_id=doctor_id,
                method="PUT",
                path="/api/test/alpha",
                status_code=200,
                payload='{"alpha": 1}',
                created_at=datetime(2040, 1, 1, 10, 0, 0),
            )
        )
        db.add(
            AuditLog(
                operator_id=admin_id,
                method="POST",
                path="/api/test/beta",
                status_code=400,
                payload='{"beta": 2}',
                created_at=datetime(2040, 1, 2, 10, 0, 0),
            )
        )
        db.commit()
    finally:
        db.close()

    response = client.get("/api/audit-logs", headers=admin_headers)
    assert response.status_code == 200
    records = response.json()
    alpha = next(item for item in records if item["request_path"] == "/api/test/alpha")
    assert alpha["operator_user_id"] == doctor_id
    assert alpha["operator_username"] == "audit_query_doctor"
    assert alpha["method"] == "PUT"
    assert alpha["status_code"] == 200
    assert alpha["payload"] == '{"alpha": 1}'
    assert alpha["operate_time"].startswith("2040-01-01T10:00:00")

    by_operator = client.get(
        "/api/audit-logs",
        params={"operator_user_id": doctor_id},
        headers=admin_headers,
    )
    assert by_operator.status_code == 200
    assert by_operator.json()
    assert all(
        item["operator_user_id"] == doctor_id for item in by_operator.json()
    )

    by_time = client.get(
        "/api/audit-logs",
        params={
            "start_time": "2040-01-01T00:00:00",
            "end_time": "2040-01-01T23:59:59",
        },
        headers=admin_headers,
    )
    paths = [item["request_path"] for item in by_time.json()]
    assert "/api/test/alpha" in paths
    assert "/api/test/beta" not in paths

    by_method_and_path = client.get(
        "/api/audit-logs",
        params={"method": "PUT", "request_path": "/api/test/alpha"},
        headers=admin_headers,
    )
    assert [item["request_path"] for item in by_method_and_path.json()] == [
        "/api/test/alpha"
    ]

    doctor_headers = _headers(
        client.post(
            "/api/auth/login",
            json={"username": "audit_query_doctor", "password": "doc123"},
        ).json()["access_token"]
    )
    assert (
        client.get("/api/audit-logs", headers=doctor_headers).status_code == 403
    )
    assert client.get("/api/audit-logs").status_code == 401
