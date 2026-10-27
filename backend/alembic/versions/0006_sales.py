"""Add sales and sale items."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0006_sales"
down_revision = "0005_products_inventory"
branch_labels = None
depends_on = None


sale_status = sa.Enum("draft", "confirmed", "cancelled", name="sale_status")


def upgrade() -> None:
    op.create_table(
        "sales",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("branch_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("branches.id"), nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("status", sale_status, server_default="draft", nullable=False),
        sa.Column("subtotal", sa.Numeric(14, 4), nullable=False),
        sa.Column("discount", sa.Numeric(14, 4), server_default="0", nullable=False),
        sa.Column("tax", sa.Numeric(14, 4), server_default="0", nullable=False),
        sa.Column("total", sa.Numeric(14, 4), nullable=False),
        sa.Column("notes", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("confirmed_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_sales_company_id", "sales", ["company_id"])
    op.create_table(
        "sale_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("sale_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("sales.id", ondelete="CASCADE"), nullable=False),
        sa.Column("product_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("products.id"), nullable=False),
        sa.Column("quantity", sa.Numeric(14, 4), nullable=False),
        sa.Column("unit_price", sa.Numeric(14, 4), nullable=False),
        sa.Column("line_total", sa.Numeric(14, 4), nullable=False),
        sa.UniqueConstraint("sale_id", "product_id", name="uq_sale_items_product"),
    )


def downgrade() -> None:
    op.drop_table("sale_items")
    op.drop_index("ix_sales_company_id", table_name="sales")
    op.drop_table("sales")
    sale_status.drop(op.get_bind(), checkfirst=True)
