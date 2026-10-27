import enum
from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, Enum, ForeignKey, Numeric, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.modules.core.models.base import Base


class AdjustmentStatus(str, enum.Enum):
    DRAFT = "draft"
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"


class AdjustmentReason(str, enum.Enum):
    MERMA = "merma"
    EXPIRATION = "vencimiento"
    DAMAGE = "danio"
    SUPPLIER_RETURN = "devolucion_proveedor"
    CORRECTION = "correccion"


class StockAdjustment(Base):
    __tablename__ = "stock_adjustments"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    company_id: Mapped[UUID] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), nullable=False)
    branch_id: Mapped[UUID] = mapped_column(ForeignKey("branches.id"), nullable=False)
    created_by: Mapped[UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    status: Mapped[AdjustmentStatus] = mapped_column(Enum(AdjustmentStatus, values_callable=lambda members: [member.value for member in members], name="adjustment_status"), nullable=False, server_default="draft")
    reason: Mapped[AdjustmentReason] = mapped_column(Enum(AdjustmentReason, values_callable=lambda members: [member.value for member in members], name="adjustment_reason"), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    items = relationship("StockAdjustmentItem", back_populates="adjustment", cascade="all, delete-orphan")


class StockAdjustmentItem(Base):
    __tablename__ = "stock_adjustment_items"
    __table_args__ = (
        UniqueConstraint("adjustment_id", "product_id", name="uq_stock_adjustment_items_product"),
        CheckConstraint("quantity > 0", name="ck_stock_adjustment_items_positive"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    adjustment_id: Mapped[UUID] = mapped_column(ForeignKey("stock_adjustments.id", ondelete="CASCADE"), nullable=False)
    product_id: Mapped[UUID] = mapped_column(ForeignKey("products.id"), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)

    adjustment = relationship("StockAdjustment", back_populates="items")
