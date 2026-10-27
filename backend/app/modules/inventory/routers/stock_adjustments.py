from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.dependencies import require_admin
from app.db import get_db
from app.models import User
from app.modules.inventory.schemas.stock_adjustment import StockAdjustmentCreate, StockAdjustmentResponse, StockReceiptCreate, StockReceiptResponse
from app.modules.inventory.services.stock_adjustment_service import confirm_adjustment, create_adjustment, list_adjustments, receive_stock


router = APIRouter(prefix="/api/inventory/adjustments", tags=["inventory"])


@router.get("", response_model=list[StockAdjustmentResponse])
def get_adjustments(user: User = Depends(require_admin), session: Session = Depends(get_db)) -> list[StockAdjustmentResponse]:
    return list_adjustments(session, user)


@router.post("", response_model=StockAdjustmentResponse, status_code=status.HTTP_201_CREATED)
def post_adjustment(data: StockAdjustmentCreate, user: User = Depends(require_admin), session: Session = Depends(get_db)) -> StockAdjustmentResponse:
    return create_adjustment(session, user, data)


@router.post("/{adjustment_id}/confirm", response_model=StockAdjustmentResponse)
def post_confirm(adjustment_id: UUID, user: User = Depends(require_admin), session: Session = Depends(get_db)) -> StockAdjustmentResponse:
    return confirm_adjustment(session, user, adjustment_id)


@router.post("/receipts", response_model=StockReceiptResponse, status_code=status.HTTP_201_CREATED)
def post_receipt(data: StockReceiptCreate, user: User = Depends(require_admin), session: Session = Depends(get_db)) -> StockReceiptResponse:
    return receive_stock(session, user, data)
