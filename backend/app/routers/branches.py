from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.dependencies import require_admin
from app.db import get_db
from app.models import Branch, User
from app.schemas.branch import BranchCreate, BranchResponse, BranchUpdate
from app.services.branch_service import create_branch, list_branches, update_branch


router = APIRouter(prefix="/api/branches", tags=["branches"])


@router.get("", response_model=list[BranchResponse])
def get_branches(user: User = Depends(require_admin), session: Session = Depends(get_db)) -> list[BranchResponse]:
    return list_branches(session, user)


@router.post("", response_model=BranchResponse, status_code=status.HTTP_201_CREATED)
def post_branch(data: BranchCreate, user: User = Depends(require_admin), session: Session = Depends(get_db)) -> BranchResponse:
    return create_branch(session, user, data)


@router.patch("/{branch_id}", response_model=BranchResponse)
def patch_branch(branch_id: UUID, data: BranchUpdate, user: User = Depends(require_admin), session: Session = Depends(get_db)) -> BranchResponse:
    return update_branch(session, user, branch_id, data)
