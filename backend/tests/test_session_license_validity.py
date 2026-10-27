"""Session validity is independent of the activation-file import deadline."""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest


@pytest.fixture
def licensing(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://test:test@127.0.0.1:1/test")
    monkeypatch.setenv("APP_ENCRYPTION_KEY", "test-only-key")
    monkeypatch.setenv("TOKEN_PEPPER", "test-only-pepper")
    from app.services import license_service
    return license_service


@pytest.mark.parametrize("start,end,accepted", [
    (-10, 10, True), (-20, -10, False), (10, 20, False),
])
def test_signed_commercial_dates(licensing, monkeypatch, start, end, accepted):
    now = datetime.now(timezone.utc)
    payload = SimpleNamespace(
        valid_from=now + timedelta(days=start),
        valid_until=now + timedelta(days=end),
        activation_expires_at=now - timedelta(days=30),
    )
    monkeypatch.setattr(licensing, "verify_stored_license", lambda *args: payload)
    monkeypatch.setattr(licensing, "verify_company_binding", lambda *args: None)
    args = (SimpleNamespace(company_id=1), SimpleNamespace(id=1),
            SimpleNamespace(clock_state_path=None))
    if accepted:
        assert licensing.verify_session_license(*args) is payload
    else:
        with pytest.raises(ValueError, match="validity period"):
            licensing.verify_session_license(*args)


def test_session_cannot_use_other_company_license(licensing):
    with pytest.raises(ValueError, match="another company"):
        licensing.verify_session_license(
            SimpleNamespace(company_id=2), SimpleNamespace(id=1), object(),
        )


def test_session_checks_clock_rollback(licensing, monkeypatch):
    now = datetime.now(timezone.utc)
    monkeypatch.setattr(licensing, "verify_stored_license", lambda *args: SimpleNamespace(
        valid_from=now - timedelta(days=1), valid_until=now + timedelta(days=1)))
    monkeypatch.setattr(licensing, "verify_company_binding", lambda *args: None)
    def rollback(path):
        raise ValueError("clock rollback")
    monkeypatch.setattr(licensing, "check_clock_state", rollback)
    with pytest.raises(ValueError, match="clock rollback"):
        licensing.verify_session_license(
            SimpleNamespace(company_id=1), SimpleNamespace(id=1),
            SimpleNamespace(clock_state_path="clock-state"),
        )


@pytest.mark.parametrize("entrypoint", ["dependency", "me"])
def test_session_entrypoints_reject_invalid_license(licensing, monkeypatch, entrypoint):
    from fastapi import HTTPException
    from app.core import dependencies
    from app.services import auth_service
    user = SimpleNamespace(is_active=True, company_id=1)
    token = SimpleNamespace(user=user, license=SimpleNamespace(company_id=1))
    session = SimpleNamespace(scalar=lambda query: token,
                              get=lambda *args: SimpleNamespace(id=1))
    def invalid(*args):
        raise ValueError("expired signed license")
    target = dependencies if entrypoint == "dependency" else auth_service
    monkeypatch.setattr(target, "verify_session_license", invalid)
    with pytest.raises(HTTPException) as exc:
        if entrypoint == "dependency":
            dependencies.get_current_user("cookie", session)
        else:
            auth_service.get_me(session, "cookie", SimpleNamespace(token_pepper=b"pepper"))
    assert exc.value.status_code == 401
    assert exc.value.detail == "Licencia inválida"
