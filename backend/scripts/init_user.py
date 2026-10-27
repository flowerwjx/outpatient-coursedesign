#!/usr/bin/env python3
"""Create the four course-design accounts for the Docker backend image.

The script is safe to run on every container start:
existing usernames are skipped and never reset.
"""

import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import app.models  # noqa: F401  (register all ORM models with Base)
from app.database import Base, SessionLocal, engine
from app.models.user import User, UserRole
from app.services.user_service import hash_password

ACCOUNTS = [
    ("admin", "admin123", UserRole.ADMIN),
    ("doctor", "doc123", UserRole.DOCTOR),
    ("cashier", "cash123", UserRole.CASHIER),
    ("pharmacist", "pha123", UserRole.PHARMACIST),
]


def main() -> int:
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    created = 0
    skipped = 0
    failed = 0

    try:
        for username, password, role in ACCOUNTS:
            try:
                existing = (
                    db.query(User).filter(User.username == username).first()
                )
                if existing is not None:
                    skipped += 1
                    print(f"[SKIP] {username} already exists")
                    continue

                db.add(
                    User(
                        username=username,
                        password_hash=hash_password(password),
                        role=role,
                    )
                )
                db.commit()
                created += 1
                print(f"[CREATE] {username} ({role.value})")
            except Exception as exc:  # noqa: BLE001
                db.rollback()
                failed += 1
                print(f"[FAIL] {username}: {exc}")
    finally:
        db.close()

    print(
        f"\nDone: created={created}, skipped={skipped}, failed={failed}"
    )
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
