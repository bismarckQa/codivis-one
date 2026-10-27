from decimal import Decimal
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.modules.sales.schemas.sale import SaleCreate, SaleItemCreate


def test_sale_calculates_subtotal_and_total_from_lines():
    sale = SaleCreate(
        branch_id=uuid4(),
        items=[
            SaleItemCreate(product_id=uuid4(), quantity=2, unit_price=Decimal("5.50")),
            SaleItemCreate(product_id=uuid4(), quantity=1, unit_price=Decimal("10.00")),
        ],
    )

    assert sale.subtotal == Decimal("21.00")
    assert sale.total == Decimal("21.00")


def test_sale_rejects_empty_or_duplicate_product_lines():
    product_id = uuid4()
    with pytest.raises(ValidationError):
        SaleCreate(branch_id=uuid4(), items=[])

    with pytest.raises(ValidationError):
        SaleCreate(
            branch_id=uuid4(),
            items=[
                SaleItemCreate(product_id=product_id, quantity=1, unit_price=10),
                SaleItemCreate(product_id=product_id, quantity=1, unit_price=10),
            ],
        )


def test_sale_rejects_invalid_values():
    with pytest.raises(ValidationError):
        SaleItemCreate(product_id=uuid4(), quantity=0, unit_price=10)
    with pytest.raises(ValidationError):
        SaleItemCreate(product_id=uuid4(), quantity=1, unit_price=-1)
