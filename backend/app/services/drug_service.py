import csv
import io
from decimal import Decimal, InvalidOperation
from typing import Optional, Sequence

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.drug import Drug
from app.models.prescription import PrescriptionItem
from app.schemas.drug import DrugCreate, DrugUpdate


class DrugServiceError(Exception):
    status_code = 400

    def __init__(self, detail: str) -> None:
        super().__init__(detail)
        self.detail = detail


class DrugNotFoundError(DrugServiceError):
    status_code = 404


class DrugConflictError(DrugServiceError):
    status_code = 409


class DrugInUseError(DrugServiceError):
    status_code = 409


_HEADER_ALIASES = {
    "generic_name": "generic_name",
    "通用名": "generic_name",
    "trade_name": "trade_name",
    "商品名": "trade_name",
    "spec": "spec",
    "规格": "spec",
    "dosage_form": "dosage_form",
    "剂型": "dosage_form",
    "insurance_type": "insurance_type",
    "医保类别": "insurance_type",
    "unit_price": "unit_price",
    "单价": "unit_price",
    "stock": "stock",
    "库存": "stock",
}

_REQUIRED_HEADERS = (
    "generic_name",
    "trade_name",
    "spec",
    "dosage_form",
    "insurance_type",
    "unit_price",
    "stock",
)


def list_drugs(
    db: Session, keyword: Optional[str] = None, limit: int = 200
) -> Sequence[Drug]:
    query = db.query(Drug)
    if keyword:
        pattern = f"%{keyword.strip()}%"
        query = query.filter(
            Drug.generic_name.like(pattern)
            | Drug.trade_name.like(pattern)
            | Drug.spec.like(pattern)
        )
    return query.order_by(Drug.id.asc()).limit(limit).all()


def create_drug(db: Session, payload: DrugCreate) -> Drug:
    drug = Drug(**payload.model_dump())
    db.add(drug)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise DrugConflictError(
            "a drug with the same generic/trade name, spec and dosage form already exists"
        ) from exc
    db.refresh(drug)
    return drug


def update_drug(db: Session, drug_id: int, payload: DrugUpdate) -> Drug:
    drug = db.get(Drug, drug_id)
    if drug is None:
        raise DrugNotFoundError("drug not found")

    changes = payload.model_dump(exclude_unset=True, exclude_none=True)
    if not changes:
        raise DrugServiceError("at least one field must be provided")

    for field, value in changes.items():
        setattr(drug, field, value)

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise DrugConflictError(
            "a drug with the same generic/trade name, spec and dosage form already exists"
        ) from exc
    db.refresh(drug)
    return drug


def delete_drug(db: Session, drug_id: int) -> None:
    drug = db.get(Drug, drug_id)
    if drug is None:
        raise DrugNotFoundError("drug not found")

    in_use = (
        db.query(PrescriptionItem.id)
        .filter(PrescriptionItem.drug_id == drug_id)
        .first()
    )
    if in_use is not None:
        raise DrugInUseError(
            "drug is referenced by prescription items and cannot be deleted"
        )

    db.delete(drug)
    db.commit()


def _canonical_headers(fieldnames: Sequence[str]) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for header in fieldnames:
        if header is None:
            continue
        key = header.strip()
        canonical = _HEADER_ALIASES.get(key) or _HEADER_ALIASES.get(key.lower())
        if canonical:
            mapping[canonical] = header
    return mapping


def _parse_drug_row(values: dict[str, str]) -> Drug:
    generic_name = values["generic_name"]
    trade_name = values["trade_name"]
    spec = values["spec"]
    dosage_form = values["dosage_form"]
    insurance_type = values["insurance_type"]
    unit_price_text = values["unit_price"]
    stock_text = values["stock"]

    if not generic_name:
        raise ValueError("通用名不能为空")
    if not spec:
        raise ValueError("规格不能为空")
    if not dosage_form:
        raise ValueError("剂型不能为空")
    if not insurance_type:
        raise ValueError("医保类别不能为空")

    if not unit_price_text:
        raise ValueError("单价不能为空")
    try:
        unit_price = Decimal(unit_price_text)
    except InvalidOperation as exc:
        raise ValueError("单价格式非法") from exc
    if not unit_price.is_finite() or unit_price < 0:
        raise ValueError("单价必须是非负数字")
    if unit_price.as_tuple().exponent < -2:
        raise ValueError("单价最多保留 2 位小数")

    if not stock_text:
        raise ValueError("库存不能为空")
    try:
        stock = int(stock_text)
    except ValueError as exc:
        raise ValueError("库存必须是整数") from exc
    if stock < 0:
        raise ValueError("库存不能为负数")

    if len(generic_name) > 100:
        raise ValueError("通用名长度不能超过 100")
    if len(trade_name) > 100:
        raise ValueError("商品名长度不能超过 100")
    if len(spec) > 100:
        raise ValueError("规格长度不能超过 100")
    if len(dosage_form) > 50:
        raise ValueError("剂型长度不能超过 50")
    if len(insurance_type) > 50:
        raise ValueError("医保类别长度不能超过 50")

    return Drug(
        generic_name=generic_name,
        trade_name=trade_name,
        spec=spec,
        dosage_form=dosage_form,
        insurance_type=insurance_type,
        unit_price=unit_price,
        stock=stock,
    )


def import_drugs_from_csv(db: Session, raw: bytes) -> dict:
    if not raw:
        raise DrugServiceError("CSV 文件为空")

    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        try:
            text = raw.decode("gb18030")
        except UnicodeDecodeError as exc:
            raise DrugServiceError(
                "CSV 文件编码必须为 UTF-8 或 GB18030"
            ) from exc

    if not text.strip():
        raise DrugServiceError("CSV 文件为空")

    reader = csv.DictReader(io.StringIO(text))
    header_map = _canonical_headers(reader.fieldnames or [])
    missing = [header for header in _REQUIRED_HEADERS if header not in header_map]
    if missing:
        raise DrugServiceError(
            "CSV 缺少必填列: " + ", ".join(missing)
        )

    success = 0
    fail = 0
    errors: list[dict] = []

    for row_number, row in enumerate(reader, start=2):
        values = {
            field: (row.get(source_header) or "").strip()
            for field, source_header in header_map.items()
        }
        if not any(values.values()):
            continue

        try:
            drug = _parse_drug_row(values)

            exists = (
                db.query(Drug.id)
                .filter(
                    Drug.generic_name == drug.generic_name,
                    Drug.trade_name == drug.trade_name,
                    Drug.spec == drug.spec,
                    Drug.dosage_form == drug.dosage_form,
                )
                .first()
            )
            if exists is not None:
                raise ValueError("药品已存在")

            db.add(drug)
            db.commit()
            success += 1
        except ValueError as exc:
            db.rollback()
            fail += 1
            errors.append({"row": row_number, "error": str(exc)})
        except IntegrityError:
            db.rollback()
            fail += 1
            errors.append({"row": row_number, "error": "药品已存在或数据冲突"})
        except Exception as exc:  # noqa: BLE001
            db.rollback()
            fail += 1
            errors.append({"row": row_number, "error": f"导入失败: {exc}"})

    return {"success": success, "fail": fail, "errors": errors}
