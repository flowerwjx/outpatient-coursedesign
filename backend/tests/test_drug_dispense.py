import itertools
import os
import sys
import tempfile
from datetime import date, timedelta
from pathlib import Path

_TMP_DIR = tempfile.mkdtemp(prefix="his_drug_dispense_test_")
os.environ["DATABASE_URL"] = "sqlite:///" + (
    Path(_TMP_DIR) / "test_drug_dispense.db"
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
from app.models.dispense_record import DispenseRecord
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

_schedule_date_seq = itertools.count(1)
_drug_seq = itertools.count(1)


def _next_schedule_date() -> date:
    return date(2038, 1, 1) + timedelta(days=next(_schedule_date_seq))


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
def pharmacist_id(client, pharmacist_headers) -> int:
    return client.get("/api/me", headers=pharmacist_headers).json()["id"]


def _drug_payload(**overrides) -> dict:
    number = next(_drug_seq)
    payload = {
        "generic_name": f"测试药品{number}",
        "trade_name": f"商品名{number}",
        "spec": "10mg×10片",
        "dosage_form": "片剂",
        "insurance_type": "甲类",
        "unit_price": "10.00",
        "stock": 100,
    }
    payload.update(overrides)
    return payload


def _create_drug(client: TestClient, admin_headers: dict, **overrides) -> dict:
    payload = _drug_payload(**overrides)
    response = client.post("/api/drugs", json=payload, headers=admin_headers)
    assert response.status_code == 201, response.text
    return response.json()


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
    client: TestClient,
    headers: dict,
    schedule_id: int,
    patient_name: str = "发药患者",
) -> dict:
    response = client.post(
        "/api/registrations",
        json={
            "patient_name": patient_name,
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
    items: list[dict],
    patient_name: str = "发药患者",
) -> dict:
    schedule = _create_schedule(client, admin_headers, doctor_id)
    registration = _register(
        client, admin_headers, schedule["id"], patient_name
    )
    response = client.post(
        "/api/prescriptions",
        json={
            "registration_id": registration["id"],
            "icd10_code": "J06.9",
            "diagnosis_name": "急性上呼吸道感染",
            "items": items,
        },
        headers=doctor_headers,
    )
    assert response.status_code == 201, response.text
    return response.json()


def _charge(client: TestClient, cashier_headers: dict, prescription_id: int):
    return client.post(
        "/api/charge-orders",
        json={"prescription_id": prescription_id},
        headers=cashier_headers,
    )


def _dispense(client: TestClient, headers: dict, prescription_id: int):
    return client.post(
        "/api/dispenses",
        json={"prescription_id": prescription_id},
        headers=headers,
    )


def _drug_stock(drug_id: int) -> int:
    db = SessionLocal()
    try:
        return db.get(Drug, drug_id).stock
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


def _prescription_paid(prescription_id: int) -> bool:
    db = SessionLocal()
    try:
        return db.get(Prescription, prescription_id).paid
    finally:
        db.close()


def _import_csv(client: TestClient, headers: dict, content: str):
    return client.post(
        "/api/drugs/import",
        files={"file": ("drugs.csv", content.encode("utf-8"), "text/csv")},
        headers=headers,
    )


def test_admin_can_create_update_delete_drug(client, admin_headers, cashier_headers):
    created = _create_drug(
        client,
        admin_headers,
        stock=50,
        unit_price="12.34",
    )

    assert created["id"] > 0
    assert created["stock"] == 50
    assert created["unit_price"] == pytest.approx(12.34)

    response = client.get(
        "/api/drugs",
        params={"keyword": created["generic_name"]},
        headers=cashier_headers,
    )
    assert response.status_code == 200
    assert created["id"] in [item["id"] for item in response.json()]

    update = client.put(
        f"/api/drugs/{created['id']}",
        json={"stock": 60, "unit_price": "13.00"},
        headers=admin_headers,
    )
    assert update.status_code == 200
    assert update.json()["stock"] == 60
    assert update.json()["unit_price"] == pytest.approx(13.00)

    delete = client.delete(
        f"/api/drugs/{created['id']}", headers=admin_headers
    )
    assert delete.status_code == 204


def test_drug_list_requires_login(client, doctor_headers):
    response = client.get("/api/drugs", headers=doctor_headers)
    assert response.status_code == 200
    assert client.get("/api/drugs").status_code == 401


def test_only_admin_can_maintain_drugs(
    client, admin_headers, doctor_headers, cashier_headers, pharmacist_headers
):
    drug = _create_drug(client, admin_headers)
    payload = _drug_payload()

    assert (
        client.post("/api/drugs", json=payload, headers=doctor_headers).status_code
        == 403
    )
    assert (
        client.put(
            f"/api/drugs/{drug['id']}",
            json={"stock": 1},
            headers=cashier_headers,
        ).status_code
        == 403
    )
    assert (
        client.delete(
            f"/api/drugs/{drug['id']}", headers=pharmacist_headers
        ).status_code
        == 403
    )
    assert client.post("/api/drugs", json=payload).status_code == 401


def test_duplicate_drug_returns_409(client, admin_headers):
    payload = _drug_payload()

    first = client.post("/api/drugs", json=payload, headers=admin_headers)
    second = client.post("/api/drugs", json=payload, headers=admin_headers)

    assert first.status_code == 201
    assert second.status_code == 409


def test_cannot_delete_drug_referenced_by_prescription(
    client, admin_headers, doctor_headers, doctor_id
):
    drug = _create_drug(client, admin_headers)
    _make_prescription(
        client,
        admin_headers,
        doctor_headers,
        doctor_id,
        items=[{"drug_id": drug["id"], "qty": 1}],
        patient_name="引用药品患者",
    )

    response = client.delete(
        f"/api/drugs/{drug['id']}", headers=admin_headers
    )

    assert response.status_code == 409
    assert "prescription" in response.json()["detail"]


def test_csv_import_partial_success(client, admin_headers):
    prefix = next(_drug_seq)
    valid_one = f"导入药品{prefix}A"
    valid_two = f"导入药品{prefix}B"
    csv_content = f"""generic_name,trade_name,spec,dosage_form,insurance_type,unit_price,stock
{valid_one},商品A,10mg×10片,片剂,甲类,12.50,10
{valid_two},,20mg×20片,胶囊剂,乙类,8.00,20
,商品C,10mg,片剂,甲类,5.00,10
导入药品{prefix}D,商品D,10mg,片剂,甲类,abc,10
导入药品{prefix}E,商品E,10mg,片剂,甲类,5.00,-1
"""

    response = _import_csv(client, admin_headers, csv_content)

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["success"] == 2
    assert body["fail"] == 3
    assert len(body["errors"]) == 3
    assert [item["row"] for item in body["errors"]] == [4, 5, 6]

    db = SessionLocal()
    try:
        names = {
            drug.generic_name
            for drug in db.query(Drug)
            .filter(Drug.generic_name.in_([valid_one, valid_two]))
            .all()
        }
    finally:
        db.close()
    assert names == {valid_one, valid_two}


def test_csv_import_missing_header_returns_400(client, admin_headers):
    csv_content = """generic_name,trade_name,spec,dosage_form,insurance_type,unit_price
药品X,商品X,10mg,片剂,甲类,5.00
"""

    response = _import_csv(client, admin_headers, csv_content)

    assert response.status_code == 400
    assert "缺少必填列" in response.json()["detail"]


def test_csv_import_rejects_unprivileged_roles(client, doctor_headers):
    csv_content = """generic_name,trade_name,spec,dosage_form,insurance_type,unit_price,stock
药品Y,商品Y,10mg,片剂,甲类,5.00,10
"""
    assert (
        _import_csv(client, doctor_headers, csv_content).status_code == 403
    )


def test_pharmacist_can_import_csv(client, pharmacist_headers):
    number = next(_drug_seq)
    name = f"药师导入药品{number}"
    csv_content = f"""generic_name,trade_name,spec,dosage_form,insurance_type,unit_price,stock
{name},商品Z,10mg,片剂,甲类,5.00,10
"""

    response = _import_csv(client, pharmacist_headers, csv_content)

    assert response.status_code == 200, response.text
    assert response.json()["success"] == 1
    assert response.json()["fail"] == 0


def test_dispense_paid_prescription_deducts_stock_and_audits(
    client,
    admin_headers,
    doctor_headers,
    cashier_headers,
    pharmacist_headers,
    doctor_id,
    pharmacist_id,
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
            {"drug_id": drug_one["id"], "qty": 3},
            {"drug_id": drug_two["id"], "qty": 2},
        ],
        patient_name="正常发药患者",
    )

    assert _charge(client, cashier_headers, prescription["id"]).status_code == 201

    response = _dispense(client, pharmacist_headers, prescription["id"])

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["prescription_id"] == prescription["id"]
    assert body["pharmacist_id"] == pharmacist_id
    assert body["pharmacist_username"] == "pharmacist"
    assert body["patient_name"] == "正常发药患者"
    stocks = {item["drug_id"]: item["remaining_stock"] for item in body["items"]}
    assert stocks[drug_one["id"]] == 7
    assert stocks[drug_two["id"]] == 8

    assert _drug_stock(drug_one["id"]) == 7
    assert _drug_stock(drug_two["id"]) == 8
    assert _dispense_count(prescription["id"]) == 1

    db = SessionLocal()
    try:
        log = (
            db.query(AuditLog)
            .filter(AuditLog.path == "/api/dispenses")
            .order_by(AuditLog.id.desc())
            .first()
        )
    finally:
        db.close()

    assert log is not None
    assert log.operator_id == pharmacist_id
    assert log.method == "POST"
    assert log.status_code == 201


def test_dispense_unpaid_prescription_returns_400(
    client, admin_headers, doctor_headers, pharmacist_headers, doctor_id
):
    drug = _create_drug(client, admin_headers, stock=10)
    prescription = _make_prescription(
        client,
        admin_headers,
        doctor_headers,
        doctor_id,
        items=[{"drug_id": drug["id"], "qty": 2}],
        patient_name="未收费发药患者",
    )

    response = _dispense(client, pharmacist_headers, prescription["id"])

    assert response.status_code == 400
    assert "paid" in response.json()["detail"]
    assert _drug_stock(drug["id"]) == 10
    assert _dispense_count(prescription["id"]) == 0


def test_dispense_insufficient_stock_rolls_back(
    client,
    admin_headers,
    doctor_headers,
    cashier_headers,
    pharmacist_headers,
    doctor_id,
):
    drug = _create_drug(client, admin_headers, stock=2)
    prescription = _make_prescription(
        client,
        admin_headers,
        doctor_headers,
        doctor_id,
        items=[{"drug_id": drug["id"], "qty": 3}],
        patient_name="库存不足患者",
    )
    assert _charge(client, cashier_headers, prescription["id"]).status_code == 201

    response = _dispense(client, pharmacist_headers, prescription["id"])

    assert response.status_code == 400
    assert "insufficient stock" in response.json()["detail"]
    assert _drug_stock(drug["id"]) == 2
    assert _dispense_count(prescription["id"]) == 0
    assert _prescription_paid(prescription["id"]) is True


def test_dispense_multi_item_rolls_back_all_stock_changes(
    client,
    admin_headers,
    doctor_headers,
    cashier_headers,
    pharmacist_headers,
    doctor_id,
):
    enough = _create_drug(client, admin_headers, stock=10)
    insufficient = _create_drug(client, admin_headers, stock=1)
    prescription = _make_prescription(
        client,
        admin_headers,
        doctor_headers,
        doctor_id,
        items=[
            {"drug_id": enough["id"], "qty": 2},
            {"drug_id": insufficient["id"], "qty": 2},
        ],
        patient_name="多药品回滚患者",
    )
    assert _charge(client, cashier_headers, prescription["id"]).status_code == 201

    response = _dispense(client, pharmacist_headers, prescription["id"])

    assert response.status_code == 400
    assert _drug_stock(enough["id"]) == 10
    assert _drug_stock(insufficient["id"]) == 1
    assert _dispense_count(prescription["id"]) == 0


def test_dispense_twice_returns_409(
    client,
    admin_headers,
    doctor_headers,
    cashier_headers,
    pharmacist_headers,
    doctor_id,
):
    drug = _create_drug(client, admin_headers, stock=5)
    prescription = _make_prescription(
        client,
        admin_headers,
        doctor_headers,
        doctor_id,
        items=[{"drug_id": drug["id"], "qty": 1}],
        patient_name="重复发药患者",
    )
    assert _charge(client, cashier_headers, prescription["id"]).status_code == 201

    first = _dispense(client, pharmacist_headers, prescription["id"])
    second = _dispense(client, pharmacist_headers, prescription["id"])

    assert first.status_code == 201
    assert second.status_code == 409
    assert _drug_stock(drug["id"]) == 4
    assert _dispense_count(prescription["id"]) == 1


def test_pharmacist_can_list_paid_prescriptions_with_dispense_status(
    client,
    admin_headers,
    doctor_headers,
    cashier_headers,
    pharmacist_headers,
    doctor_id,
):
    drug = _create_drug(client, admin_headers, stock=5)
    prescription = _make_prescription(
        client,
        admin_headers,
        doctor_headers,
        doctor_id,
        items=[{"drug_id": drug["id"], "qty": 1}],
        patient_name="药房列表患者",
    )
    assert _charge(client, cashier_headers, prescription["id"]).status_code == 201

    before = client.get(
        "/api/prescriptions",
        params={"paid": "true"},
        headers=pharmacist_headers,
    )
    assert before.status_code == 200
    before_record = next(
        item for item in before.json() if item["id"] == prescription["id"]
    )
    assert before_record["paid"] is True
    assert before_record["dispensed"] is False
    assert before_record["dispense_id"] is None

    dispense = _dispense(client, pharmacist_headers, prescription["id"])
    assert dispense.status_code == 201
    dispense_id = dispense.json()["id"]

    after = client.get(
        "/api/prescriptions",
        params={"paid": "true"},
        headers=pharmacist_headers,
    )
    after_record = next(
        item for item in after.json() if item["id"] == prescription["id"]
    )
    assert after_record["dispensed"] is True
    assert after_record["dispense_id"] == dispense_id

    assert (
        client.get(
            "/api/prescriptions",
            params={"paid": "true"},
            headers=doctor_headers,
        ).status_code
        == 403
    )


def test_only_pharmacist_can_dispense(
    client,
    admin_headers,
    doctor_headers,
    cashier_headers,
    pharmacist_headers,
    doctor_id,
):
    drug = _create_drug(client, admin_headers, stock=5)
    prescription = _make_prescription(
        client,
        admin_headers,
        doctor_headers,
        doctor_id,
        items=[{"drug_id": drug["id"], "qty": 1}],
        patient_name="发药权限患者",
    )
    assert _charge(client, cashier_headers, prescription["id"]).status_code == 201

    assert (
        _dispense(client, admin_headers, prescription["id"]).status_code == 403
    )
    assert (
        _dispense(client, doctor_headers, prescription["id"]).status_code == 403
    )
    assert (
        _dispense(client, cashier_headers, prescription["id"]).status_code == 403
    )
    assert (
        client.post(
            "/api/dispenses", json={"prescription_id": prescription["id"]}
        ).status_code
        == 401
    )

    assert _drug_stock(drug["id"]) == 5
    assert _dispense_count(prescription["id"]) == 0


def test_drug_stock_cannot_be_negative_via_api(client, admin_headers):
    create = client.post(
        "/api/drugs",
        json=_drug_payload(stock=-1),
        headers=admin_headers,
    )
    assert create.status_code == 422

    drug = _create_drug(client, admin_headers, stock=1)
    update = client.put(
        f"/api/drugs/{drug['id']}",
        json={"stock": -1},
        headers=admin_headers,
    )
    assert update.status_code == 422
