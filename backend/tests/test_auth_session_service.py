from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from sqlalchemy.dialects import postgresql


@pytest.fixture
def service(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://test:test@127.0.0.1:1/test")
    monkeypatch.setenv("APP_ENCRYPTION_KEY", "test-only-key")
    monkeypatch.setenv("TOKEN_PEPPER", "test-only-pepper")
    from app.services import auth_service
    return auth_service


@pytest.mark.parametrize("admin", [True, False])
def test_me_blocks_disabled_user(service, admin):
    token = SimpleNamespace(user=SimpleNamespace(is_active=False, is_admin=admin), license=object())
    session = SimpleNamespace(scalar=lambda query: token)
    with pytest.raises(HTTPException) as error:
        service.get_me(session, "cookie", SimpleNamespace(token_pepper=b"pepper"))
    assert error.value.status_code == 401
    assert error.value.detail == "Usuario desactivado"


def test_me_blocks_missing_company(service):
    token = SimpleNamespace(user=SimpleNamespace(is_active=True, company_id="missing"), license=object())
    session = SimpleNamespace(scalar=lambda query: token, get=lambda *args: None)
    with pytest.raises(HTTPException) as error:
        service.get_me(session, "cookie", SimpleNamespace(token_pepper=b"pepper"))
    assert error.value.status_code == 401
    assert error.value.detail == "Empresa no disponible"


def test_logout_limits_revocation_to_matching_session(service):
    calls = []
    session = SimpleNamespace(execute=lambda query: calls.append(query), commit=lambda: calls.append("commit"))
    service.logout(session, "secret-cookie", SimpleNamespace(token_pepper=b"pepper"))
    assert len(calls) == 2 and calls[1] == "commit"
    statement = calls[0].compile(dialect=postgresql.dialect())
    assert service.digest("secret-cookie", b"pepper") in statement.params.values()
    assert "session" in statement.params.values()
    assert "revoked_at IS NULL" in str(statement)
    assert "secret-cookie" not in statement.params.values()
