"""Query isolation and pagination; these do not replace PostgreSQL integration."""
from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy.dialects import postgresql


@pytest.fixture
def stock_routes(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://test:test@127.0.0.1:1/test")
    monkeypatch.setenv("APP_ENCRYPTION_KEY", "test-only-key")
    monkeypatch.setenv("TOKEN_PEPPER", "test-only-pepper")
    from app.modules.inventory.routers import stock
    return stock


@pytest.mark.parametrize("endpoint", ["get_balances", "get_movements"])
def test_reads_scope_company_and_filters_with_pagination(stock_routes, endpoint):
    company, branch, product = uuid4(), uuid4(), uuid4()
    statements = []
    def scalars(statement):
        statements.append(statement)
        return SimpleNamespace(all=lambda: [])
    result = getattr(stock_routes, endpoint)(
        branch_id=branch, product_id=product, limit=20, offset=40,
        user=SimpleNamespace(company_id=company),
        session=SimpleNamespace(scalars=scalars),
    )
    assert result == []
    compiled = statements[0].compile(dialect=postgresql.dialect())
    assert {company, branch, product, 20, 40} <= set(compiled.params.values())
    assert "company_id =" in str(compiled)
    assert "branch_id =" in str(compiled)
    assert "product_id =" in str(compiled)
    assert "ORDER BY" in str(compiled)


def test_inventory_routes_enforce_bounded_pagination(stock_routes):
    from fastapi import FastAPI
    app = FastAPI()
    app.include_router(stock_routes.router)
    paths = app.openapi()["paths"]
    for path in ("/api/inventory/balances", "/api/inventory/movements"):
        parameters = {p["name"]: p["schema"] for p in paths[path]["get"]["parameters"]}
        assert parameters["limit"]["minimum"] == 1
        assert parameters["limit"]["maximum"] == 500
        assert parameters["offset"]["minimum"] == 0


def test_movement_type_filters_history(stock_routes):
    from app.modules.inventory.models.stock import MovementType
    statements = []

    def scalars(statement):
        statements.append(statement)
        return SimpleNamespace(all=lambda: [])

    stock_routes.get_movements(
        branch_id=None, product_id=None, movement_type=MovementType.IN,
        limit=10, offset=0, user=SimpleNamespace(company_id=uuid4()),
        session=SimpleNamespace(scalars=scalars),
    )
    compiled = statements[0].compile(dialect=postgresql.dialect())
    assert "movement_type =" in str(compiled)
    assert "in" in compiled.params.values()
