from types import SimpleNamespace
import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from app.modules.core.schemas.branch import BranchCreate, BranchUpdate

@pytest.mark.parametrize("payload", [{"name": None}, {"is_active": None}, {}, {"unknown": 1}, {"name": "   "}])
def test_invalid_branch_update(payload):
    with pytest.raises(ValidationError):
        BranchUpdate(**payload)

def test_partial_update_preserves_false():
    assert BranchUpdate(is_active=False).model_dump(exclude_unset=True) == {"is_active": False}

def test_create_rejects_extra():
    with pytest.raises(ValidationError):
        BranchCreate(name="Central", unknown=1)

def test_name_normalized():
    assert BranchCreate(name="  Central  ").name == "Central"

@pytest.mark.parametrize("admin", [False, True])
def test_inactive_user_rejected_before_license_validation(admin, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://test:test@127.0.0.1:1/test")
    monkeypatch.setenv("APP_ENCRYPTION_KEY", "test-only-key")
    monkeypatch.setenv("TOKEN_PEPPER", "test-only-pepper")
    from app.core import dependencies as deps
    user = SimpleNamespace(is_active=False, is_admin=admin)
    token = SimpleNamespace(user=user, license=object())
    session = SimpleNamespace(scalar=lambda query: token)
    with pytest.raises(HTTPException) as exc:
        deps.get_current_user("session-cookie", session)
    assert exc.value.status_code == 401
    assert exc.value.detail == "Usuario desactivado"
