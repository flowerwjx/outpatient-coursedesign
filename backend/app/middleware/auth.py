import time
from typing import Iterable, List, Optional, Union

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from app.config import ACCESS_TOKEN_EXPIRE_MINUTES, JWT_ALGORITHM, JWT_SECRET
from app.database import get_db
from app.models.user import User, UserRole
from app.services import user_service

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

_CREDENTIALS_EXCEPTION = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Could not validate credentials",
    headers={"WWW-Authenticate": "Bearer"},
)


def create_access_token(user: User, expires_delta: Optional[int] = None) -> str:
    expire_seconds = (
        expires_delta
        if expires_delta is not None
        else ACCESS_TOKEN_EXPIRE_MINUTES * 60
    )
    payload = {
        "sub": str(user.id),
        "user_id": user.id,
        "role": user.role.value,
        "exp": int(time.time()) + expire_seconds,
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def get_current_user(
    request: Request,
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        user_id = payload.get("user_id")
        role = payload.get("role")
        if user_id is None or role is None:
            raise _CREDENTIALS_EXCEPTION
        token_role = UserRole(role)
    except (JWTError, ValueError, TypeError):
        raise _CREDENTIALS_EXCEPTION

    user = user_service.get_by_id(db, int(user_id))
    if user is None or user.role != token_role:
        raise _CREDENTIALS_EXCEPTION

    # Consumed by the audit middleware to record the operator of write requests.
    request.state.user_id = user.id
    return user


def require_role(allowed_roles: Union[Iterable[UserRole], Iterable[str]]):
    allowed = {
        role.value if isinstance(role, UserRole) else str(role)
        for role in allowed_roles
    }

    def dependency(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role.value not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not enough permissions",
            )
        return current_user

    return dependency
