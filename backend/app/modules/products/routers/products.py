from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user, require_admin
from app.db import get_db
from app.models import Product, User
from app.modules.products.schemas.product import ProductCreate, ProductResponse, ProductUpdate
from app.modules.products.services.product_service import create_product, list_products, update_product


router = APIRouter(prefix="/api/products", tags=["products"])


@router.get("", response_model=list[ProductResponse])
def get_products(user: User = Depends(get_current_user), session: Session = Depends(get_db)) -> list[ProductResponse]:
    return list_products(session, user)


@router.post("", response_model=ProductResponse, status_code=status.HTTP_201_CREATED)
def post_product(data: ProductCreate, user: User = Depends(require_admin), session: Session = Depends(get_db)) -> ProductResponse:
    return create_product(session, user, data)


@router.patch("/{product_id}", response_model=ProductResponse)
def patch_product(product_id: UUID, data: ProductUpdate, user: User = Depends(require_admin), session: Session = Depends(get_db)) -> ProductResponse:
    return update_product(session, user, product_id, data)

