from typing import Optional

from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    Query,
    UploadFile,
    status,
)
from sqlalchemy.orm import Session

from app.database import get_db
from app.middleware.auth import get_current_user, require_role
from app.models.user import User
from app.schemas.drug import (
    DrugCreate,
    DrugImportResult,
    DrugOut,
    DrugUpdate,
)
from app.services import drug_service

router = APIRouter(prefix="/api/drugs", tags=["drugs"])

_MAX_CSV_BYTES = 5 * 1024 * 1024


def _raise_http(exc: drug_service.DrugServiceError) -> None:
    raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc


@router.get("", response_model=list[DrugOut])
def list_drugs(
    keyword: Optional[str] = Query(default=None, max_length=100),
    limit: int = Query(default=200, ge=1, le=500),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> list[DrugOut]:
    return list(drug_service.list_drugs(db, keyword=keyword, limit=limit))


@router.post("", response_model=DrugOut, status_code=status.HTTP_201_CREATED)
def create_drug(
    payload: DrugCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_role(["admin"])),
) -> DrugOut:
    try:
        return drug_service.create_drug(db, payload)
    except drug_service.DrugServiceError as exc:
        _raise_http(exc)


@router.post("/import", response_model=DrugImportResult)
async def import_drugs(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    _: User = Depends(require_role(["admin", "pharmacist"])),
) -> DrugImportResult:
    raw = await file.read()
    if len(raw) > _MAX_CSV_BYTES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="CSV file is too large (max 5MB)",
        )
    try:
        return drug_service.import_drugs_from_csv(db, raw)
    except drug_service.DrugServiceError as exc:
        _raise_http(exc)


@router.put("/{drug_id}", response_model=DrugOut)
def update_drug(
    drug_id: int,
    payload: DrugUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_role(["admin"])),
) -> DrugOut:
    try:
        return drug_service.update_drug(db, drug_id, payload)
    except drug_service.DrugServiceError as exc:
        _raise_http(exc)


@router.delete("/{drug_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_drug(
    drug_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_role(["admin"])),
):
    try:
        drug_service.delete_drug(db, drug_id)
    except drug_service.DrugServiceError as exc:
        _raise_http(exc)
