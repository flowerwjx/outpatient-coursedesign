#!/usr/bin/env python3
"""Create or refresh the four course-design test accounts.

Accounts:
    admin      / admin123   (admin)
    doctor     / doc123     (doctor)
    cashier    / cash123    (cashier)
    pharmacist / pha123     (pharmacist)

The script is idempotent: existing accounts are updated to the listed
password and role instead of failing.
"""

import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1] / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

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
    updated = 0
    failed = 0

    try:
        for username, password, role in ACCOUNTS:
            try:
                user = db.query(User).filter(User.username == username).first()
                password_hash = hash_password(password)
                if user is None:
                    db.add(
                        User(
                            username=username,
                            password_hash=password_hash,
                            role=role,
                        )
                    )
                    db.commit()
                    created += 1
                    print(f"[CREATE] {username} / {password} ({role.value})")
                else:
                    user.password_hash = password_hash
                    user.role = role
                    db.commit()
                    updated += 1
                    print(f"[UPDATE] {username} / {password} ({role.value})")
            except Exception as exc:  # noqa: BLE001
                db.rollback()
                failed += 1
                print(f"[FAIL] {username}: {exc}")
    finally:
        db.close()

    print(f"\nDone: created={created}, updated={updated}, failed={failed}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
