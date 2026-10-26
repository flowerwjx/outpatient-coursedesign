import os
import sys
import tempfile
from pathlib import Path

_TMP_DIR = tempfile.mkdtemp(prefix="his_auth_test_")
os.environ["DATABASE_URL"] = "sqlite:///" + (Path(_TMP_DIR) / "test_auth.db").as_posix()
os.environ.setdefault("JWT_SECRET", "test-only-secret")

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import pytest
from fastapi import Depends
from fastapi.testclient import TestClient
from jose import jwt

from app.config import JWT_ALGORITHM, JWT_SECRET
from app.database import Base, SessionLocal, engine
from app.main import app
from app.middleware.auth import require_role
from app.models.audit import AuditLog
from app.models.user import User, UserRole
from app.services.user_service import create_user

ACCOUNTS = [
    ("admin", "admin123", UserRole.ADMIN),
    ("doctor", "doc123", UserRole.DOCTOR),
    ("cashier", "cash123", UserRole.CASHIER),
    ("pharmacist", "pha123", UserRole.PHARMACIST),
]


@app.get("/api/_test_admin_only")
def _test_admin_only(current_user: User = Depends(require_role(["admin"]))):
    return {"username": current_user.username}


@pytest.fixture(scope="module")
def client():
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


def _login(client, username, password):
    return client.post(
        "/api/auth/login",
        json={"username": username, "password": password},
    )


def _auth_header(token):
    return {"Authorization": f"Bearer {token}"}


def test_login_returns_token_with_user_id_and_role(client):
    response = _login(client, "admin", "admin123")
    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"

    payload = jwt.decode(body["access_token"], JWT_SECRET, algorithms=[JWT_ALGORITHM])
    assert payload["user_id"] == 1
    assert payload["role"] == "admin"
    assert "exp" in payload


def test_login_accepts_form_data_for_swagger(client):
    response = client.post(
        "/api/auth/login",
        data={"username": "admin", "password": "admin123"},
    )
    assert response.status_code == 200
    assert "access_token" in response.json()


def test_login_is_audited_and_password_redacted(client):
    assert _login(client, "cashier", "cash123").status_code == 200

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
    assert log.operator_id is not None
    assert log.status_code == 200
    assert "cash123" not in (log.payload or "")
    assert "***" in (log.payload or "")


def test_me_returns_current_user(client):
    token = _login(client, "doctor", "doc123").json()["access_token"]
    response = client.get("/api/me", headers=_auth_header(token))
    assert response.status_code == 200
    assert response.json()["username"] == "doctor"
    assert response.json()["role"] == "doctor"


def test_me_without_token_returns_401(client):
    assert client.get("/api/me").status_code == 401


def test_me_with_invalid_token_returns_401(client):
    assert client.get("/api/me", headers=_auth_header("not.a.token")).status_code == 401


def test_login_with_wrong_password_returns_401(client):
    assert _login(client, "admin", "wrong-password").status_code == 401


def test_login_with_unknown_user_returns_401(client):
    assert _login(client, "nobody", "whatever").status_code == 401


def test_require_role_allows_matching_role(client):
    token = _login(client, "admin", "admin123").json()["access_token"]
    response = client.get("/api/_test_admin_only", headers=_auth_header(token))
    assert response.status_code == 200


def test_require_role_rejects_other_role_with_403(client):
    token = _login(client, "doctor", "doc123").json()["access_token"]
    response = client.get("/api/_test_admin_only", headers=_auth_header(token))
    assert response.status_code == 403


def test_require_role_without_login_returns_401(client):
    assert client.get("/api/_test_admin_only").status_code == 401


@pytest.mark.parametrize("username,password,role", [
    ("cashier", "cash123", "cashier"),
    ("pharmacist", "pha123", "pharmacist"),
])
def test_all_seeded_accounts_can_login(client, username, password, role):
    response = _login(client, username, password)
    assert response.status_code == 200
    me = client.get("/api/me", headers=_auth_header(response.json()["access_token"]))
    assert me.status_code == 200
    assert me.json()["role"] == role
