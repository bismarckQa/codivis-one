"""Add database checks for product, inventory and sales amounts."""
from alembic import op


revision = "0007_integrity_constraints"
down_revision = "0006_sales"
branch_labels = None
depends_on = None


CONSTRAINTS = {
    "products": [("ck_products_prices_nonnegative", "price >= 0 AND cost >= 0")],
    "stock_balances": [("ck_stock_balances_nonnegative", "quantity >= 0")],
    "stock_movements": [("ck_stock_movements_positive", "quantity > 0")],
    "stock_adjustment_items": [("ck_stock_adjustment_items_positive", "quantity > 0")],
    "sales": [
        ("ck_sales_amounts_nonnegative", "subtotal >= 0 AND discount >= 0 AND tax >= 0 AND total >= 0"),
        ("ck_sales_discount_not_over_subtotal", "discount <= subtotal"),
        ("ck_sales_total_matches_amounts", "total = subtotal - discount + tax"),
    ],
    "sale_items": [("ck_sale_items_amounts", "quantity > 0 AND unit_price >= 0 AND line_total >= 0")],
}


def upgrade() -> None:
    for table, constraints in CONSTRAINTS.items():
        for name, expression in constraints:
            op.create_check_constraint(name, table, expression)


def downgrade() -> None:
    for table, constraints in reversed(list(CONSTRAINTS.items())):
        for name, _expression in reversed(constraints):
            op.drop_constraint(name, table_name=table, type_="check")
