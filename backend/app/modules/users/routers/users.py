from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.dependencies import require_admin
from app.db import get_db
from app.models import User
from app.schemas.user import UserCreate, UserResponse, UserUpdate
from app.modules.users.services.user_service import create_user, list_users, update_user


router = APIRouter(prefix="/api/users", tags=["users"])


@router.get("", response_model=list[UserResponse])
def get_users(user: User = Depends(require_admin), session: Session = Depends(get_db)) -> list[UserResponse]:
    return list_users(session, user)


@router.post("", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def post_user(data: UserCreate, user: User = Depends(require_admin), session: Session = Depends(get_db)) -> UserResponse:
    return create_user(session, user, data)


@router.patch("/{user_id}", response_model=UserResponse)
def patch_user(user_id: UUID, data: UserUpdate, user: User = Depends(require_admin), session: Session = Depends(get_db)) -> UserResponse:
    return update_user(session, user, user_id, data)
