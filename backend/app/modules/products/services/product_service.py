from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Product, User
from app.modules.products.schemas.product import ProductCreate, ProductUpdate


PRODUCT_CODE_CONSTRAINT = "uq_products_company_code"


def _is_constraint(error: IntegrityError, constraint_name: str) -> bool:
    return getattr(getattr(error, "orig", None), "diag", None) is not None and getattr(error.orig.diag, "constraint_name", None) == constraint_name


def list_products(session: Session, user: User) -> list[Product]:
    return list(session.scalars(select(Product).where(Product.company_id == user.company_id, Product.is_active.is_(True)).order_by(Product.name)).all())


def create_product(session: Session, user: User, data: ProductCreate) -> Product:
    if session.scalar(select(Product).where(Product.company_id == user.company_id, Product.code == data.code)):
        raise HTTPException(409, "Ya existe un producto con ese código")
    product = Product(id=uuid4(), company_id=user.company_id, **data.model_dump())
    session.add(product)
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        if _is_constraint(exc, PRODUCT_CODE_CONSTRAINT):
            raise HTTPException(409, "Ya existe un producto con ese código") from exc
        raise
    session.refresh(product)
    return product


def update_product(session: Session, user: User, product_id, data: ProductUpdate) -> Product:
    product = session.scalar(select(Product).where(Product.id == product_id, Product.company_id == user.company_id))
    if product is None:
        raise HTTPException(404, "Producto no encontrado")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(product, field, value)
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        if _is_constraint(exc, PRODUCT_CODE_CONSTRAINT):
            raise HTTPException(409, "Ya existe un producto con ese código") from exc
        raise
    session.refresh(product)
    return product
