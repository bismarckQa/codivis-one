from datetime import datetime, timezone
from uuid import UUID, uuid4

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import Branch, Product, User
from app.modules.inventory.models.stock import MovementType, StockBalance, StockMovement
from app.modules.inventory.services.stock_lock import lock_company_products
from app.modules.sales.models.sale import Sale, SaleItem, SaleStatus
from app.modules.sales.schemas.sale import SaleCreate


def list_sales(session: Session, user: User) -> list[Sale]:
    statement = select(Sale).options(selectinload(Sale.items)).where(Sale.company_id == user.company_id).order_by(Sale.created_at.desc())
    return list(session.scalars(statement).all())


def create_sale(session: Session, user: User, data: SaleCreate) -> Sale:
    if session.scalar(select(Branch).where(Branch.id == data.branch_id, Branch.company_id == user.company_id)) is None:
        raise HTTPException(404, "Sucursal no encontrada")
    product_ids = [item.product_id for item in data.items]
    products = list(session.scalars(select(Product).where(Product.company_id == user.company_id, Product.id.in_(product_ids))).all())
    if len(products) != len(product_ids):
        raise HTTPException(404, "Uno o más productos no pertenecen a esta instalación")
    sale = Sale(id=uuid4(), company_id=user.company_id, branch_id=data.branch_id, created_by=user.id, subtotal=data.subtotal, discount=data.discount, tax=data.tax, total=data.total, notes=data.notes)
    sale.items = [SaleItem(id=uuid4(), product_id=item.product_id, quantity=item.quantity, unit_price=item.unit_price, line_total=item.line_total) for item in data.items]
    session.add(sale)
    session.commit()
    session.refresh(sale)
    return sale


def confirm_sale(session: Session, user: User, sale_id: UUID) -> Sale:
    sale = session.scalar(select(Sale).options(selectinload(Sale.items)).where(Sale.id == sale_id, Sale.company_id == user.company_id).with_for_update())
    if sale is None:
        raise HTTPException(404, "Venta no encontrada")
    if sale.status != SaleStatus.DRAFT:
        raise HTTPException(409, "Solo se puede confirmar una venta en borrador")

    lock_company_products(session, user.company_id, [item.product_id for item in sale.items])
    for item in sorted(sale.items, key=lambda value: str(value.product_id)):
        balance = session.scalar(select(StockBalance).where(StockBalance.company_id == user.company_id, StockBalance.branch_id == sale.branch_id, StockBalance.product_id == item.product_id).with_for_update())
        if balance is None or balance.quantity < item.quantity:
            session.rollback()
            raise HTTPException(409, "La venta supera el stock disponible")
        balance.quantity -= item.quantity
        session.add(StockMovement(id=uuid4(), company_id=user.company_id, branch_id=sale.branch_id, product_id=item.product_id, movement_type=MovementType.OUT, quantity=item.quantity, reference_type="sale", reference_id=sale.id))

    sale.status = SaleStatus.CONFIRMED
    sale.confirmed_at = datetime.now(timezone.utc)
    session.commit()
    session.refresh(sale)
    return sale


def cancel_sale(session: Session, user: User, sale_id: UUID) -> Sale:
    sale = session.scalar(select(Sale).where(Sale.id == sale_id, Sale.company_id == user.company_id).with_for_update())
    if sale is None:
        raise HTTPException(404, "Venta no encontrada")
    if sale.status != SaleStatus.DRAFT:
        raise HTTPException(409, "Solo se puede cancelar una venta en borrador")
    sale.status = SaleStatus.CANCELLED
    session.commit()
    session.refresh(sale)
    return sale
