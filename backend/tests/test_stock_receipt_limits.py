"""Limits must match the PostgreSQL movement and balance columns."""
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app.modules.inventory.schemas.stock_adjustment import StockReceiptCreate
from app.modules.inventory.services import stock_adjustment_service as service


def test_receipt_notes_match_movement_column():
    payload = dict(branch_id=uuid4(), items=[dict(product_id=uuid4(), quantity='1')])
    assert len(StockReceiptCreate(**payload, notes='x' * 120).notes) == 120
    with pytest.raises(ValidationError):
        StockReceiptCreate(**payload, notes='x' * 121)


@pytest.mark.parametrize('current,quantity,overflow', [
    ('9999999999.9998', '0.0001', False),
    ('9999999999.9999', '0.0001', True),
])
def test_receipt_checks_accumulated_balance(monkeypatch, current, quantity, overflow):
    product_id = uuid4()
    data = StockReceiptCreate(branch_id=uuid4(), items=[dict(product_id=product_id, quantity=quantity)])
    balance = SimpleNamespace(quantity=Decimal(current))
    scalar_results = iter([object(), balance])
    list_results = iter([[object()], []])
    events = []
    session = SimpleNamespace(
        scalar=lambda _: next(scalar_results),
        scalars=lambda _: SimpleNamespace(all=lambda: next(list_results)),
        add=lambda _: events.append('add'),
        commit=lambda: events.append('commit'),
        rollback=lambda: events.append('rollback'),
    )
    monkeypatch.setattr(service, 'lock_company_products', lambda *args: None)
    monkeypatch.setattr(service, 'lock_receipt_operation', lambda *args: None)
    if overflow:
        with pytest.raises(HTTPException) as error:
            service.receive_stock(session, SimpleNamespace(company_id=uuid4()), data)
        assert error.value.status_code == 409
        assert events == ['rollback']
        assert balance.quantity == Decimal(current)
    else:
        service.receive_stock(session, SimpleNamespace(company_id=uuid4()), data)
        assert balance.quantity == Decimal('9999999999.9999')
        assert events == ['add', 'commit']
