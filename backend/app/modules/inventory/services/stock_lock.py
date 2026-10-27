from hashlib import blake2b
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select, text
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


def lock_receipt_operation(session: Session, company_id: UUID, operation_id: UUID) -> None:
    """Hold a PostgreSQL transaction lock across receipt lookup and persistence.

    Product locks alone cannot serialize retries containing different products.
    A stable digest avoids Python's process-specific hash and scopes the lock to
    this installation's receipt operation. PostgreSQL releases it at transaction end.
    """
    key = int.from_bytes(blake2b(
        f"stock_receipt:{company_id}:{operation_id}".encode(), digest_size=8,
    ).digest(), byteorder="big", signed=True)
    session.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": key})
