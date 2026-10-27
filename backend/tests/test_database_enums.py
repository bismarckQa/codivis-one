import pytest
from sqlalchemy.dialects import postgresql
from app.modules.sales.models.sale import Sale, SaleStatus
from app.modules.inventory.models.stock import StockMovement, MovementType
from app.modules.inventory.models.stock_adjustment import StockAdjustment, AdjustmentStatus, AdjustmentReason
from app.modules.inventory.models.stock import StockBalance
from app.modules.sales.models.sale import SaleItem

@pytest.mark.parametrize("model,field,members", [
    (Sale, "status", SaleStatus),
    (StockMovement, "movement_type", MovementType),
    (StockAdjustment, "status", AdjustmentStatus),
    (StockAdjustment, "reason", AdjustmentReason),
])
def test_postgresql_enum_roundtrip_uses_migration_values(model, field, members):
    column_type = model.__table__.c[field].type
    dialect = postgresql.dialect()
    encode = column_type.bind_processor(dialect)
    decode = column_type.result_processor(dialect, None)
    assert column_type.enums == [member.value for member in members]
    for member in members:
        assert encode(member) == member.value
        assert decode(member.value) is member


def test_inventory_and_sale_models_declare_database_uniqueness():
    stock_constraints = {constraint.name for constraint in StockBalance.__table__.constraints}
    sale_constraints = {constraint.name for constraint in SaleItem.__table__.constraints}
    assert "uq_stock_balances_location_product" in stock_constraints
    assert "uq_sale_items_product" in sale_constraints
