"""Receipt retries must preserve the original operation payload."""
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.modules.inventory.schemas.stock_adjustment import StockReceiptCreate
from app.modules.inventory.services import stock_adjustment_service as service


@pytest.mark.parametrize('changed', [None, 'branch', 'notes', 'quantity'])
def test_receipt_retry_checks_full_payload(monkeypatch, changed):
    branch_id, product_id = uuid4(), uuid4()
    data = StockReceiptCreate(branch_id=branch_id, notes='Entrada inicial',
                              items=[dict(product_id=product_id, quantity='2')])
    movement = SimpleNamespace(product_id=product_id, quantity=data.items[0].quantity,
                               branch_id=branch_id, reason=data.notes)
    if changed == 'branch':
        movement.branch_id = uuid4()
    elif changed == 'notes':
        movement.reason = 'Otra entrada'
    elif changed == 'quantity':
        movement.quantity += 1
    results = iter([[SimpleNamespace(id=product_id)], [movement]])
    session = SimpleNamespace(
        scalar=lambda statement: SimpleNamespace(id=branch_id),
        scalars=lambda statement: SimpleNamespace(all=lambda: next(results)),
    )
    monkeypatch.setattr(service, 'lock_company_products', lambda *args: None)
    monkeypatch.setattr(service, 'lock_receipt_operation', lambda *args: None)
    user = SimpleNamespace(company_id=uuid4())
    if changed:
        with pytest.raises(HTTPException) as error:
            service.receive_stock(session, user, data)
        assert error.value.status_code == 409
    else:
        response = service.receive_stock(session, user, data)
        assert response.operation_id == data.operation_id
        assert response.branch_id == branch_id
        assert response.items == data.items
