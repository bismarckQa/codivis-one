from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user, require_admin
from app.db import get_db
from app.models import User
from app.modules.sales.schemas.sale import SaleCreate, SaleResponse
from app.modules.sales.services.sale_service import cancel_sale, confirm_sale, create_sale, list_sales


router = APIRouter(prefix="/api/sales", tags=["sales"])


@router.get("", response_model=list[SaleResponse])
def get_sales(user: User = Depends(get_current_user), session: Session = Depends(get_db)) -> list[SaleResponse]:
    return list_sales(session, user)


@router.post("", response_model=SaleResponse, status_code=status.HTTP_201_CREATED)
def post_sale(data: SaleCreate, user: User = Depends(require_admin), session: Session = Depends(get_db)) -> SaleResponse:
    return create_sale(session, user, data)


@router.post("/{sale_id}/confirm", response_model=SaleResponse)
def post_confirm_sale(sale_id: UUID, user: User = Depends(require_admin), session: Session = Depends(get_db)) -> SaleResponse:
    return confirm_sale(session, user, sale_id)


@router.post("/{sale_id}/cancel", response_model=SaleResponse)
def post_cancel_sale(sale_id: UUID, user: User = Depends(require_admin), session: Session = Depends(get_db)) -> SaleResponse:
    return cancel_sale(session, user, sale_id)

