from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.config import ACCESS_TOKEN_EXPIRE_MINUTES
from app.database import get_db
from app.middleware.auth import create_access_token, get_current_user
from app.models.user import User
from app.schemas.user import LoginRequest, Token, UserOut
from app.services import user_service

router = APIRouter(tags=["auth"])


async def _parse_login_payload(request: Request) -> LoginRequest:
    content_type = request.headers.get("content-type", "")
    if "application/json" in content_type:
        data = await request.json()
    else:
        form = await request.form()
        data = {"username": form.get("username"), "password": form.get("password")}
    return LoginRequest(**data)


@router.post("/api/auth/login", response_model=Token)
def login(
    request: Request,
    payload: LoginRequest = Depends(_parse_login_payload),
    db: Session = Depends(get_db),
) -> Token:
    user = user_service.authenticate(db, payload.username, payload.password)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    request.state.user_id = user.id
    access_token = create_access_token(user)
    return Token(
        access_token=access_token,
        token_type="bearer",
        expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.get("/api/me", response_model=UserOut)
def read_me(current_user: User = Depends(get_current_user)) -> UserOut:
    return current_user
