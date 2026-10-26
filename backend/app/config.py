import os
from pathlib import Path
from typing import List

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _load_dotenv(path: Path) -> None:
    if not path.is_file():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


for _candidate in (PROJECT_ROOT / ".env", PROJECT_ROOT / "backend" / ".env"):
    _load_dotenv(_candidate)

JWT_SECRET = os.getenv("JWT_SECRET", "")
if not JWT_SECRET:
    raise RuntimeError("JWT_SECRET is not set. Configure it in the environment or .env file.")

JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "120"))

_database_url = os.getenv("DATABASE_URL", "sqlite:///./his.db")
if _database_url.startswith("sqlite:///./"):
    _relative = _database_url[len("sqlite:///./"):]
    _absolute = (PROJECT_ROOT / _relative).resolve()
    _database_url = "sqlite:///" + str(_absolute).replace("\\", "/")
DATABASE_URL = _database_url

CORS_ALLOW_ORIGINS: List[str] = [
    origin.strip()
    for origin in os.getenv("CORS_ALLOW_ORIGINS", "").split(",")
    if origin.strip()
]
