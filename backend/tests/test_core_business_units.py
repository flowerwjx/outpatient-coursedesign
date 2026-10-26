import os
import sys
import tempfile
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

_TMP_DIR = tempfile.mkdtemp(prefix="his_unit_test_")
os.environ["DATABASE_URL"] = "sqlite:///" + (
    Path(_TMP_DIR) / "test_unit.db"
).as_posix()
os.environ.setdefault("JWT_SECRET", "test-only-secret")

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401
from app.database import Base
from app.models.drug import Drug
from app.models.prescription import PrescriptionItem
from app.services.charge_service import (
    DrugNotFoundError,
    InvalidChargeDataError,
    _calculate_total,
)
from app.services.dispense_service import (
    DrugNotFoundError as DispenseDrugNotFoundError,
    InsufficientStockError,
    InvalidDispenseDataError,
    deduct_stock,
)


class _FakeQuery:
    def __init__(self, rows):
        self.rows = rows

    def filter(self, *args, **kwargs):
        return self

    def all(self):
        return self.rows


class _FakeSession:
    def __init__(self, items, drugs):
        self.items = items
        self.drugs = drugs

    def query(self, model):
        if model is PrescriptionItem:
            return _FakeQuery(self.items)
        if model is Drug:
            return _FakeQuery(self.drugs)
        raise AssertionError(f"unexpected model: {model}")


@pytest.fixture
def db():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = Session()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def _new_drug(db, *, stock: int = 10) -> Drug:
    drug = Drug(
        generic_name="单元测试药品",
        trade_name="测试商品名",
        spec="10mg×10片",
        dosage_form="片剂",
        insurance_type="甲类",
        unit_price=Decimal("12.50"),
        stock=stock,
    )
    db.add(drug)
    db.commit()
    db.refresh(drug)
    return drug


def test_calculate_total_normal():
    items = [
        SimpleNamespace(drug_id=1, qty=2),
        SimpleNamespace(drug_id=2, qty=1),
    ]
    drugs = [
        SimpleNamespace(
            id=1,
            unit_price=Decimal("12.50"),
            generic_name="药品A",
            trade_name="",
            spec="10mg",
            dosage_form="片剂",
            insurance_type="甲类",
        ),
        SimpleNamespace(
            id=2,
            unit_price=Decimal("3.20"),
            generic_name="药品B",
            trade_name="",
            spec="20mg",
            dosage_form="胶囊剂",
            insurance_type="乙类",
        ),
    ]
    prescription = SimpleNamespace(id=1)

    total = _calculate_total(_FakeSession(items, drugs), prescription)

    assert total == Decimal("28.20")


def test_calculate_total_with_zero_quantity_raises():
    items = [SimpleNamespace(drug_id=1, qty=0)]
    drugs = [SimpleNamespace(id=1, unit_price=Decimal("12.50"))]
    prescription = SimpleNamespace(id=1)

    with pytest.raises(InvalidChargeDataError):
        _calculate_total(_FakeSession(items, drugs), prescription)


def test_calculate_total_with_missing_drug_raises():
    items = [SimpleNamespace(drug_id=999, qty=2)]
    prescription = SimpleNamespace(id=1)

    with pytest.raises(DrugNotFoundError):
        _calculate_total(_FakeSession(items, []), prescription)


def test_deduct_stock_normal(db):
    drug = _new_drug(db, stock=10)

    deducted = deduct_stock(db, drug.id, 3)

    assert deducted == 3
    db.expire_all()
    assert db.get(Drug, drug.id).stock == 7


def test_deduct_stock_zero_stock_raises(db):
    drug = _new_drug(db, stock=0)

    with pytest.raises(InsufficientStockError):
        deduct_stock(db, drug.id, 1)

    db.expire_all()
    assert db.get(Drug, drug.id).stock == 0


def test_deduct_stock_zero_quantity_raises(db):
    drug = _new_drug(db, stock=10)

    with pytest.raises(InvalidDispenseDataError):
        deduct_stock(db, drug.id, 0)

    db.expire_all()
    assert db.get(Drug, drug.id).stock == 10


def test_deduct_stock_missing_drug_raises(db):
    with pytest.raises(DispenseDrugNotFoundError):
        deduct_stock(db, 999999, 1)
