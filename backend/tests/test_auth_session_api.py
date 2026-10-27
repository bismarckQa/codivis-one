"""HTTP/session regressions; database calls are substituted, not PostgreSQL tests."""
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.dialects import postgresql


@pytest.fixture
def auth_api(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://test:test@127.0.0.1:1/test")
    monkeypatch.setenv("APP_ENCRYPTION_KEY", "test-only-key")
    monkeypatch.setenv("TOKEN_PEPPER", "test-only-pepper")
    from app.routers.auth import router
    from app.db import get_db

    calls = []
    session = SimpleNamespace(
        execute=lambda query: calls.append(query),
        commit=lambda: calls.append("commit"),
    )
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_db] = lambda: session
    with TestClient(app) as client:
        yield client, session, calls


def test_logout_revokes_session_and_clears_cookie(auth_api):
    from app.core.security import digest
    from app.db import settings

    client, _, calls = auth_api
    client.cookies.set("codivis_one_session", "secret-session")
    response = client.post("/api/auth/logout")
    assert response.status_code == 204
    assert response.content == b""
    cookie = response.headers["set-cookie"]
    assert 'codivis_one_session=""' in cookie
    assert "Max-Age=0" in cookie and "HttpOnly" in cookie and "Path=/" in cookie
    assert len(calls) == 2 and calls[1] == "commit"
    statement = calls[0].compile(dialect=postgresql.dialect())
    assert digest("secret-session", settings.token_pepper) in statement.params.values()
    assert "session" in statement.params.values()
    assert "revoked_at IS NULL" in str(statement)
    assert "secret-session" not in statement.params.values()


def test_logout_without_cookie_is_idempotent(auth_api):
    client, _, calls = auth_api
    for _ in range(2):
        assert client.post("/api/auth/logout").status_code == 204
    assert calls == []


def test_me_requires_cookie(auth_api):
    client, _, _ = auth_api
    assert client.get("/api/auth/me").status_code == 401


@pytest.mark.parametrize("admin", [False, True])
def test_me_rejects_inactive_users_before_license_access(auth_api, admin):
    client, session, _ = auth_api
    session.scalar = lambda query: SimpleNamespace(
        user=SimpleNamespace(is_active=False, is_admin=admin), license=object(),
    )
    client.cookies.set("codivis_one_session", "session")
    response = client.get("/api/auth/me")
    assert response.status_code == 401
    assert response.json() == {"detail": "Usuario desactivado"}


def test_me_rejects_missing_company(auth_api):
    client, session, _ = auth_api
    session.scalar = lambda query: SimpleNamespace(
        user=SimpleNamespace(is_active=True, company_id="missing"), license=object(),
    )
    session.get = lambda model, identity: None
    client.cookies.set("codivis_one_session", "session")
    response = client.get("/api/auth/me")
    assert response.status_code == 401
    assert response.json() == {"detail": "Empresa no disponible"}
