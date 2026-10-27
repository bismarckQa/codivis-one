"""Add products, stock balances, movements and inventory adjustments."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0005_products_inventory"
down_revision = "0004_branch_controls"
branch_labels = None
depends_on = None


movement_type = sa.Enum("in", "out", "adjustment_in", "adjustment_out", name="movement_type")
adjustment_status = sa.Enum("draft", "confirmed", "cancelled", name="adjustment_status")
adjustment_reason = sa.Enum("merma", "vencimiento", "danio", "devolucion_proveedor", "correccion", name="adjustment_reason")


def upgrade() -> None:
    op.create_table("products", sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True), sa.Column("company_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False), sa.Column("code", sa.String(100), nullable=False), sa.Column("name", sa.String(255), nullable=False), sa.Column("price", sa.Numeric(14, 4), server_default="0", nullable=False), sa.Column("cost", sa.Numeric(14, 4), server_default="0", nullable=False), sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False), sa.UniqueConstraint("company_id", "code", name="uq_products_company_code"), if_not_exists=True)
    op.create_index("ix_products_company_id", "products", ["company_id"])
    op.create_table("stock_balances", sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True), sa.Column("company_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False), sa.Column("branch_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("branches.id", ondelete="CASCADE"), nullable=False), sa.Column("product_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("products.id", ondelete="CASCADE"), nullable=False), sa.Column("quantity", sa.Numeric(14, 4), server_default="0", nullable=False), sa.UniqueConstraint("company_id", "branch_id", "product_id", name="uq_stock_balances_location_product"), if_not_exists=True)
    op.create_table("stock_movements", sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True), sa.Column("company_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False), sa.Column("branch_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("branches.id"), nullable=False), sa.Column("product_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("products.id"), nullable=False), sa.Column("movement_type", movement_type, nullable=False), sa.Column("quantity", sa.Numeric(14, 4), nullable=False), sa.Column("reference_type", sa.String(50), nullable=False), sa.Column("reference_id", postgresql.UUID(as_uuid=True), nullable=False), sa.Column("reason", sa.String(120)), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False), if_not_exists=True)
    op.create_table("stock_adjustments", sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True), sa.Column("company_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False), sa.Column("branch_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("branches.id"), nullable=False), sa.Column("created_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False), sa.Column("status", adjustment_status, server_default="draft", nullable=False), sa.Column("reason", adjustment_reason, nullable=False), sa.Column("notes", sa.Text()), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False), sa.Column("confirmed_at", sa.DateTime(timezone=True)), if_not_exists=True)
    op.create_table("stock_adjustment_items", sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True), sa.Column("adjustment_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("stock_adjustments.id", ondelete="CASCADE"), nullable=False), sa.Column("product_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("products.id"), nullable=False), sa.Column("quantity", sa.Numeric(14, 4), nullable=False), sa.UniqueConstraint("adjustment_id", "product_id", name="uq_stock_adjustment_items_product"), if_not_exists=True)


def downgrade() -> None:
    op.drop_table("stock_adjustment_items")
    op.drop_table("stock_adjustments")
    op.drop_table("stock_movements")
    op.drop_table("stock_balances")
    op.drop_index("ix_products_company_id", table_name="products")
    op.drop_table("products")
