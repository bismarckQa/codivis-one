from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.db import get_db
from app.models import User
from app.modules.directory.schemas.customer import CustomerCreate, CustomerResponse, CustomerUpdate
from app.modules.directory.services.customer_service import create_customer, list_customers, update_customer


router = APIRouter(prefix="/api/customers", tags=["customers"])


@router.get("", response_model=list[CustomerResponse])
def get_customers(
    search: str | None = Query(default=None, max_length=100),
    limit: int = Query(default=50, ge=1, le=100),
    user: User = Depends(get_current_user),
    session: Session = Depends(get_db),
) -> list[CustomerResponse]:
    return list_customers(session, user, search, limit)


@router.post("", response_model=CustomerResponse, status_code=status.HTTP_201_CREATED)
def post_customer(data: CustomerCreate, user: User = Depends(get_current_user), session: Session = Depends(get_db)) -> CustomerResponse:
    return create_customer(session, user, data)


@router.patch("/{customer_id}", response_model=CustomerResponse)
def patch_customer(customer_id: UUID, data: CustomerUpdate, user: User = Depends(get_current_user), session: Session = Depends(get_db)) -> CustomerResponse:
    return update_customer(session, user, customer_id, data)
