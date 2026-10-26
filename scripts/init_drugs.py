#!/usr/bin/env python3
"""Seed the demo drug archive used by prescription charging.

The IDs match the frontend doctor workstation demo catalog. The script is
idempotent: existing rows are updated in place instead of being duplicated.
"""

import sys
from decimal import Decimal
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1] / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import app.models  # noqa: F401  (register all ORM models with Base)
from app.database import Base, SessionLocal, engine
from app.models.drug import Drug

DRUGS = [
    (1, "阿莫西林胶囊", "阿莫仙", "0.25g×24粒", "胶囊剂", "甲类", "18.50", 100),
    (2, "布洛芬缓释胶囊", "芬必得", "0.3g×20粒", "胶囊剂", "乙类", "22.80", 100),
    (3, "对乙酰氨基酚片", "扑热息痛", "0.5g×20片", "片剂", "甲类", "6.50", 200),
    (4, "头孢克肟分散片", "世福素", "0.1g×12片", "分散片", "乙类", "36.00", 80),
    (5, "氯雷他定片", "开瑞坦", "10mg×6片", "片剂", "乙类", "15.60", 120),
    (6, "奥美拉唑肠溶胶囊", "洛赛克", "20mg×14粒", "肠溶胶囊", "甲类", "28.90", 90),
    (7, "蒙脱石散", "思密达", "3g×10袋", "散剂", "甲类", "19.90", 100),
    (8, "氨溴索口服溶液", "沐舒坦", "100ml", "口服溶液", "乙类", "25.40", 60),
    (9, "复方甘草片", "", "100片", "片剂", "甲类", "9.80", 150),
    (10, "维生素C片", "", "0.1g×100片", "片剂", "甲类", "4.20", 200),
    (11, "硝苯地平控释片", "拜新同", "30mg×7片", "控释片", "甲类", "32.50", 90),
    (12, "二甲双胍缓释片", "格华止", "0.5g×30片", "缓释片", "甲类", "26.70", 80),
]


def main() -> int:
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    created = 0
    updated = 0
    failed = 0

    try:
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
            try:
                drug = db.get(Drug, drug_id)
                if drug is None:
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
                    created += 1
                    print(f"[CREATE] #{drug_id} {generic_name} {unit_price}")
                else:
                    drug.generic_name = generic_name
                    drug.trade_name = trade_name
                    drug.spec = spec
                    drug.dosage_form = dosage_form
                    drug.insurance_type = insurance_type
                    drug.unit_price = Decimal(unit_price)
                    drug.stock = stock
                    updated += 1
                    print(f"[UPDATE] #{drug_id} {generic_name} {unit_price}")
                db.commit()
            except Exception as exc:  # noqa: BLE001
                db.rollback()
                failed += 1
                print(f"[FAIL] #{drug_id} {generic_name}: {exc}")
    finally:
        db.close()

    print(f"\nDone: created={created}, updated={updated}, failed={failed}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
