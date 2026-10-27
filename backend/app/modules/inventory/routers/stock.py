from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.db import get_db
from app.models import User
from app.modules.inventory.models.stock import MovementType, StockBalance, StockMovement
from app.modules.inventory.schemas.stock import StockBalanceResponse, StockMovementResponse


router = APIRouter(prefix="/api/inventory", tags=["inventory"])


def stock_query(model, company_id, branch_id=None, product_id=None):
    query = select(model).where(model.company_id == company_id)
    if branch_id is not None:
        query = query.where(model.branch_id == branch_id)
    if product_id is not None:
        query = query.where(model.product_id == product_id)
    return query


@router.get("/balances", response_model=list[StockBalanceResponse])
def get_balances(
    branch_id: UUID | None = None,
    product_id: UUID | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    user: User = Depends(get_current_user),
    session: Session = Depends(get_db),
):
    query = stock_query(StockBalance, user.company_id, branch_id, product_id)
    return list(session.scalars(query.order_by(StockBalance.id).limit(limit).offset(offset)).all())


@router.get("/movements", response_model=list[StockMovementResponse])
def get_movements(
    branch_id: UUID | None = None,
    product_id: UUID | None = None,
    movement_type: MovementType | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    user: User = Depends(get_current_user),
    session: Session = Depends(get_db),
):
    query = stock_query(StockMovement, user.company_id, branch_id, product_id)
    if movement_type is not None:
        query = query.where(StockMovement.movement_type == movement_type)
    return list(session.scalars(query.order_by(StockMovement.created_at.desc(), StockMovement.id.desc()).limit(limit).offset(offset)).all())
