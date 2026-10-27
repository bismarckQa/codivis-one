"""HTTP contracts for the single-company installation; no real database involved."""
import asyncio
from types import SimpleNamespace
from uuid import uuid4

import httpx
import pytest
from fastapi import FastAPI, HTTPException
from sqlalchemy.dialects import postgresql


@pytest.fixture
def inventory_api(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://test:test@127.0.0.1:1/test")
    monkeypatch.setenv("APP_ENCRYPTION_KEY", "test-only-key")
    monkeypatch.setenv("TOKEN_PEPPER", "test-only-pepper")
    from app.modules.inventory.routers import stock

    app = FastAPI()
    app.include_router(stock.router)
    statements = []
    company_id = uuid4()

    def scalars(statement):
        statements.append(statement)
        return SimpleNamespace(all=lambda: [])

    def current_user():
        return SimpleNamespace(company_id=company_id)

    app.dependency_overrides[stock.get_current_user] = current_user
    app.dependency_overrides[stock.get_db] = lambda: SimpleNamespace(scalars=scalars)

    def request(path):
        async def run():
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app), base_url="http://test"
            ) as client:
                return await client.get(path)
        return asyncio.run(run())

    return app, stock, request, statements, company_id


@pytest.mark.parametrize("endpoint", ["balances", "movements"])
@pytest.mark.parametrize("query", ["limit=0", "limit=501", "offset=-1", "branch_id=bad", "product_id=bad"])
def test_invalid_query_rejected_before_database(inventory_api, endpoint, query):
    _, _, request, statements, _ = inventory_api
    assert request(f"/api/inventory/{endpoint}?{query}").status_code == 422
    assert statements == []


def test_movement_type_filter_uses_validated_enum(inventory_api):
    _, _, request, statements, company_id = inventory_api
    response = request("/api/inventory/movements?movement_type=in&limit=10&offset=2")
    assert response.status_code == 200
    assert response.json() == []
    compiled = statements[0].compile(dialect=postgresql.dialect())
    assert company_id in compiled.params.values()
    assert "in" in compiled.params.values()
    assert "movement_type =" in str(compiled)


def test_invalid_movement_type_rejected(inventory_api):
    _, _, request, statements, _ = inventory_api
    assert request("/api/inventory/movements?movement_type=invalid").status_code == 422
    assert statements == []


@pytest.mark.parametrize("endpoint", ["balances", "movements"])
def test_queries_require_authenticated_session(inventory_api, endpoint):
    app, stock, request, statements, _ = inventory_api

    def reject_session():
        raise HTTPException(status_code=401, detail="Sesión requerida")

    app.dependency_overrides[stock.get_current_user] = reject_session
    assert request(f"/api/inventory/{endpoint}").status_code == 401
    assert statements == []
