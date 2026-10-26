import json
from typing import Any, Optional

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

from app.database import SessionLocal
from app.models.audit import AuditLog

_AUDITED_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
_SENSITIVE_KEYS = ("password", "token", "secret")


def _redact(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: ("***" if any(s in key.lower() for s in _SENSITIVE_KEYS) else _redact(item))
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_redact(item) for item in value]
    return value


def _summarize_body(body: bytes, content_type: str) -> Optional[str]:
    if not body:
        return None
    try:
        if "application/json" in content_type:
            data = json.loads(body.decode("utf-8"))
            return json.dumps(_redact(data), ensure_ascii=False)[:1000]
        if "application/x-www-form-urlencoded" in content_type or "multipart/form-data" in content_type:
            text = body.decode("utf-8", errors="ignore")
            pairs = []
            for part in text.split("&"):
                if "=" in part:
                    key, _, value = part.partition("=")
                    if any(s in key.lower() for s in _SENSITIVE_KEYS):
                        value = "***"
                    pairs.append(f"{key}={value}")
            return "&".join(pairs)[:1000]
        return body.decode("utf-8", errors="ignore")[:1000]
    except (ValueError, UnicodeDecodeError):
        return "<unparseable body>"


class AuditMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        if request.method not in _AUDITED_METHODS:
            return await call_next(request)

        body = await request.body()
        if body:
            async def receive():
                return {"type": "http.request", "body": body, "more_body": False}

            request._receive = receive

        response = await call_next(request)

        operator_id = getattr(request.state, "user_id", None)
        payload = _summarize_body(body, request.headers.get("content-type", ""))

        db = SessionLocal()
        try:
            db.add(
                AuditLog(
                    operator_id=operator_id,
                    method=request.method,
                    path=request.url.path,
                    status_code=response.status_code,
                    payload=payload,
                )
            )
            db.commit()
        except Exception:  # noqa: BLE001
            db.rollback()
        finally:
            db.close()

        return response
