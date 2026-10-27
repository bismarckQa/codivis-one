"""Prevent duplicate stock movements for the same operation and product."""
from alembic import op


revision = "0008_stock_operation_idempotency"
down_revision = "0007_integrity_constraints"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_stock_movement_operation_product",
        "stock_movements",
        ["company_id", "reference_type", "reference_id", "product_id"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_stock_movement_operation_product", "stock_movements", type_="unique")
