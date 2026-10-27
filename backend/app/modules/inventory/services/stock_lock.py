from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Product


def lock_company_products(session: Session, company_id: UUID, product_ids: list[UUID]) -> None:
    """Serialize stock writers through the product rows, including absent balances."""
    ordered_ids = sorted(set(product_ids), key=str)
    if not ordered_ids:
        return
    rows = list(session.scalars(select(Product.id).where(Product.company_id == company_id, Product.id.in_(ordered_ids)).order_by(Product.id).with_for_update()).all())
    if len(rows) != len(ordered_ids):
        raise HTTPException(404, "Uno o más productos no pertenecen a esta instalación")
