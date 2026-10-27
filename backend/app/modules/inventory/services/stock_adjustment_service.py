from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID, uuid4

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import Branch, Product, User
from app.modules.inventory.models.stock import MovementType, StockBalance, StockMovement
from app.modules.inventory.models.stock_adjustment import AdjustmentStatus, StockAdjustment, StockAdjustmentItem
from app.modules.inventory.schemas.stock_adjustment import StockAdjustmentCreate, StockReceiptCreate, StockReceiptResponse, StockReceiptItemCreate
from app.modules.inventory.services.stock_lock import lock_company_products, lock_receipt_operation


def list_adjustments(session: Session, user: User) -> list[StockAdjustment]:
    return list(session.scalars(select(StockAdjustment).options(selectinload(StockAdjustment.items)).where(StockAdjustment.company_id == user.company_id).order_by(StockAdjustment.created_at.desc())).all())


def create_adjustment(session: Session, user: User, data: StockAdjustmentCreate) -> StockAdjustment:
    if session.scalar(select(Branch).where(Branch.id == data.branch_id, Branch.company_id == user.company_id)) is None:
        raise HTTPException(404, "Sucursal no encontrada")
    product_ids = [item.product_id for item in data.items]
    products = list(session.scalars(select(Product).where(Product.company_id == user.company_id, Product.id.in_(product_ids))).all())
    if len(products) != len(product_ids):
        raise HTTPException(404, "Uno o más productos no pertenecen a esta instalación")
    lock_company_products(session, user.company_id, product_ids)
    adjustment = StockAdjustment(id=uuid4(), company_id=user.company_id, branch_id=data.branch_id, created_by=user.id, reason=data.reason, notes=data.notes)
    adjustment.items = [StockAdjustmentItem(id=uuid4(), product_id=item.product_id, quantity=item.quantity) for item in data.items]
    session.add(adjustment)
    session.commit()
    session.refresh(adjustment)
    return adjustment


def confirm_adjustment(session: Session, user: User, adjustment_id: UUID) -> StockAdjustment:
    adjustment = session.scalar(select(StockAdjustment).options(selectinload(StockAdjustment.items)).where(StockAdjustment.id == adjustment_id, StockAdjustment.company_id == user.company_id).with_for_update())
    if adjustment is None:
        raise HTTPException(404, "Ajuste no encontrado")
    if adjustment.status != AdjustmentStatus.DRAFT:
        raise HTTPException(409, "Solo se puede confirmar un ajuste en borrador")
    lock_company_products(session, user.company_id, [item.product_id for item in adjustment.items])
    for item in adjustment.items:
        balance = session.scalar(select(StockBalance).where(StockBalance.company_id == user.company_id, StockBalance.branch_id == adjustment.branch_id, StockBalance.product_id == item.product_id).with_for_update())
        if balance is None:
            balance = StockBalance(id=uuid4(), company_id=user.company_id, branch_id=adjustment.branch_id, product_id=item.product_id, quantity=Decimal("0"))
            session.add(balance)
            session.flush()
        if balance.quantity < item.quantity:
            session.rollback()
            raise HTTPException(409, "La merma supera el stock disponible")
        balance.quantity -= item.quantity
        session.add(StockMovement(id=uuid4(), company_id=user.company_id, branch_id=adjustment.branch_id, product_id=item.product_id, movement_type=MovementType.ADJUSTMENT_OUT, quantity=item.quantity, reference_type="stock_adjustment", reference_id=adjustment.id, reason=adjustment.reason.value))
    adjustment.status = AdjustmentStatus.CONFIRMED
    adjustment.confirmed_at = datetime.now(timezone.utc)
    session.commit()
    session.refresh(adjustment)
    return adjustment


def receive_stock(session: Session, user: User, data: StockReceiptCreate) -> StockReceiptResponse:
    if session.scalar(select(Branch).where(Branch.id == data.branch_id, Branch.company_id == user.company_id)) is None:
        raise HTTPException(404, "Sucursal no encontrada")
    product_ids = [item.product_id for item in data.items]
    products = list(session.scalars(select(Product).where(Product.company_id == user.company_id, Product.id.in_(product_ids))).all())
    if len(products) != len(product_ids):
        raise HTTPException(404, "Uno o más productos no pertenecen a esta instalación")

    lock_receipt_operation(session, user.company_id, data.operation_id)
    lock_company_products(session, user.company_id, product_ids)
    existing = list(session.scalars(select(StockMovement).where(
        StockMovement.company_id == user.company_id,
        StockMovement.reference_type == "stock_receipt",
        StockMovement.reference_id == data.operation_id,
    )).all())
    if existing:
        existing_by_product = {movement.product_id: movement.quantity for movement in existing}
        requested = {item.product_id: item.quantity for item in data.items}
        if (existing_by_product != requested
                or any(movement.branch_id != data.branch_id or movement.reason != data.notes
                       for movement in existing)):
            raise HTTPException(409, "La operación de entrada ya existe con otros datos")
        return StockReceiptResponse(
            operation_id=data.operation_id,
            branch_id=data.branch_id,
            items=[StockReceiptItemCreate(product_id=product_id, quantity=quantity) for product_id, quantity in requested.items()],
        )

    for item in sorted(data.items, key=lambda value: str(value.product_id)):
        balance = session.scalar(select(StockBalance).where(
            StockBalance.company_id == user.company_id,
            StockBalance.branch_id == data.branch_id,
            StockBalance.product_id == item.product_id,
        ).with_for_update())
        if balance is None:
            balance = StockBalance(id=uuid4(), company_id=user.company_id, branch_id=data.branch_id, product_id=item.product_id, quantity=Decimal("0"))
            session.add(balance)
            session.flush()
        new_quantity = balance.quantity + item.quantity
        if new_quantity > Decimal("9999999999.9999"):
            session.rollback()
            raise HTTPException(409, "La entrada supera la capacidad máxima de existencias")
        balance.quantity = new_quantity
        session.add(StockMovement(
            id=uuid4(), company_id=user.company_id, branch_id=data.branch_id, product_id=item.product_id,
            movement_type=MovementType.IN, quantity=item.quantity, reference_type="stock_receipt",
            reference_id=data.operation_id, reason=data.notes,
        ))
    session.commit()
    return StockReceiptResponse(operation_id=data.operation_id, branch_id=data.branch_id, items=data.items)
