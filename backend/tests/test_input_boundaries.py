from decimal import Decimal
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.modules.directory.schemas.customer import CustomerCreate, CustomerUpdate
from app.modules.products.schemas.product import ProductCreate
from app.modules.sales.schemas.sale import SaleCreate, SaleItemCreate
from app.modules.inventory.schemas.stock_adjustment import StockAdjustmentCreate, StockAdjustmentItemCreate


@pytest.mark.parametrize('field', ['name', 'is_active'])
def test_customer_update_rejects_null_required_columns(field):
    with pytest.raises(ValidationError):
        CustomerUpdate(**{field: None})


def test_customer_update_preserves_nullable_field_clear():
    assert CustomerUpdate(email=None).model_dump(exclude_unset=True) == {'email': None}


@pytest.mark.parametrize(('schema', 'values'), [
    (CustomerCreate, {'name': 'Cliente'}),
    (CustomerUpdate, {'name': 'Cliente'}),
    (ProductCreate, {'code': 'A', 'name': 'Producto'}),
    (SaleItemCreate, {'product_id': uuid4(), 'quantity': 1, 'unit_price': 1}),
    (SaleCreate, {'branch_id': uuid4(), 'items': [{'product_id': uuid4(), 'quantity': 1, 'unit_price': 1}]}),
    (StockAdjustmentItemCreate, {'product_id': uuid4(), 'quantity': 1}),
    (StockAdjustmentCreate, {'branch_id': uuid4(), 'reason': 'merma', 'items': [{'product_id': uuid4(), 'quantity': 1}]}),
])
def test_write_inputs_reject_unknown_fields(schema, values):
    with pytest.raises(ValidationError):
        schema(**values, unexpected=True)


@pytest.mark.parametrize(('quantity', 'price'), [
    ('9999999999', '2'),
    ('0.0001', '0.0001'),
])
def test_sale_rejects_line_values_that_database_cannot_preserve(quantity, price):
    with pytest.raises(ValidationError):
        SaleItemCreate(product_id=uuid4(), quantity=quantity, unit_price=price)


@pytest.mark.parametrize('tax', ['0', '9999999999'])
def test_sale_rejects_aggregate_overflow(tax):
    items = [{'product_id': uuid4(), 'quantity': 1, 'unit_price': '5000000000'}]
    if tax == '0':
        items.append({'product_id': uuid4(), 'quantity': 1, 'unit_price': '5000000000'})
    with pytest.raises(ValidationError):
        SaleCreate(branch_id=uuid4(), items=items, tax=tax)


def test_sale_accepts_exact_storage_boundary():
    sale = SaleCreate(branch_id=uuid4(), items=[{'product_id': uuid4(), 'quantity': 1, 'unit_price': '9999999999.9999'}])
    assert sale.total == Decimal('9999999999.9999')


@pytest.mark.parametrize('value', ['NaN', 'Infinity', '-Infinity'])
def test_product_rejects_non_finite_prices(value):
    with pytest.raises(ValidationError):
        ProductCreate(code='A', name='Producto', price=value)
