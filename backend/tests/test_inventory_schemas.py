import pytest
from pydantic import ValidationError

from app.modules.inventory.schemas.stock_adjustment import StockAdjustmentCreate, StockAdjustmentItemCreate
from app.modules.products.schemas.product import ProductCreate, ProductUpdate


def test_product_normalizes_code_and_name_and_rejects_negative_values():
    product = ProductCreate(code=" sku-1 ", name="  Leche ", price=2.5, cost=1.5)
    assert product.code == "SKU-1"
    assert product.name == "Leche"
    with pytest.raises(ValidationError):
        ProductCreate(code="SKU-2", name="Pan", price=-1)


def test_merma_requires_positive_items_and_reason():
    adjustment = StockAdjustmentCreate(
        branch_id="2b7f8d83-83a8-4c0c-a8bb-fb1d5e0fb3d8",
        reason="merma",
        items=[StockAdjustmentItemCreate(product_id="2b7f8d83-83a8-4c0c-a8bb-fb1d5e0fb3d8", quantity=2)],
    )
    assert adjustment.reason == "merma"
    with pytest.raises(ValidationError):
        StockAdjustmentCreate(branch_id=adjustment.branch_id, reason="merma", items=[])
    with pytest.raises(ValidationError):
        StockAdjustmentItemCreate(product_id=adjustment.items[0].product_id, quantity=0)


def test_product_update_normalizes_partial_values_and_rejects_empty_update():
    update = ProductUpdate(code=" sku-2 ", name="  Pan ", price="3.25")
    assert update.code == "SKU-2"
    assert update.name == "Pan"
    assert update.price == 3.25
    with pytest.raises(ValidationError):
        ProductUpdate()
    with pytest.raises(ValidationError):
        ProductUpdate(name=None)


def test_product_code_length_is_checked_after_normalization():
    with pytest.raises(ValidationError):
        ProductCreate(code="ß" * 100, name="Producto")
    with pytest.raises(ValidationError):
        ProductUpdate(code="ß" * 100)
