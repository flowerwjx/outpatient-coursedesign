#!/usr/bin/env python3
"""Rename legacy audit_logs columns without dropping existing data."""

import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1] / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import app.models  # noqa: F401
from app.database import Base, engine

RENAMES = (
    ("operator_id", "operator_user_id"),
    ("path", "request_path"),
    ("created_at", "operate_time"),
)


def main() -> int:
    if engine.dialect.name != "sqlite":
        print("This migration script only supports SQLite.")
        return 1

    Base.metadata.create_all(bind=engine)

    with engine.begin() as connection:
        rows = connection.exec_driver_sql("PRAGMA table_info(audit_logs)").fetchall()
        columns = {row[1] for row in rows}
        if not columns:
            print("audit_logs table does not exist; created with current schema.")
            return 0

        for old_name, new_name in RENAMES:
            if new_name in columns:
                print(f"[SKIP] {new_name} already exists")
            elif old_name in columns:
                connection.exec_driver_sql(
                    f'ALTER TABLE audit_logs RENAME COLUMN "{old_name}" '
                    f'TO "{new_name}"'
                )
                columns.remove(old_name)
                columns.add(new_name)
                print(f"[RENAME] {old_name} -> {new_name}")
            else:
                print(f"[MISS] {old_name} and {new_name} both missing")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
