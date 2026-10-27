import enum
from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, Enum, ForeignKey, Numeric, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.modules.core.models.base import Base


class SaleStatus(str, enum.Enum):
    DRAFT = "draft"
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"


class Sale(Base):
    __tablename__ = "sales"
    __table_args__ = (
        CheckConstraint("subtotal >= 0 AND discount >= 0 AND tax >= 0 AND total >= 0", name="ck_sales_amounts_nonnegative"),
        CheckConstraint("discount <= subtotal", name="ck_sales_discount_not_over_subtotal"),
        CheckConstraint("total = subtotal - discount + tax", name="ck_sales_total_matches_amounts"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    company_id: Mapped[UUID] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    branch_id: Mapped[UUID] = mapped_column(ForeignKey("branches.id"), nullable=False)
    created_by: Mapped[UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    status: Mapped[SaleStatus] = mapped_column(Enum(SaleStatus, values_callable=lambda members: [member.value for member in members], name="sale_status"), nullable=False, server_default="draft")
    subtotal: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)
    discount: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False, server_default="0")
    tax: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False, server_default="0")
    total: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    items = relationship("SaleItem", back_populates="sale", cascade="all, delete-orphan")


class SaleItem(Base):
    __tablename__ = "sale_items"
    __table_args__ = (
        UniqueConstraint("sale_id", "product_id", name="uq_sale_items_product"),
        CheckConstraint("quantity > 0 AND unit_price >= 0 AND line_total >= 0", name="ck_sale_items_amounts"),
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    sale_id: Mapped[UUID] = mapped_column(ForeignKey("sales.id", ondelete="CASCADE"), nullable=False)
    product_id: Mapped[UUID] = mapped_column(ForeignKey("products.id"), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)
    line_total: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)

    sale = relationship("Sale", back_populates="items")
