from datetime import datetime, timedelta, timezone
import base64

import pytest
from pydantic import ValidationError

from app.schemas.branch import BranchCreate, BranchUpdate
from app.schemas.company import CompanyCreate
from app.schemas.user import UserCreate
from app.schemas.license import LicensePayload


def license_payload() -> dict:
    now = datetime.now(timezone.utc)
    return {
        "license_id": "2b7f8d83-83a8-4c0c-a8bb-fb1d5e0fb3d8",
        "company_name": "Empresa Demo",
        "edition": "base",
        "modules": ["dashboard"],
        "max_users": 3,
        "max_branches": 1,
        "created_at": now,
        "activation_expires_at": now + timedelta(minutes=30),
        "valid_from": now,
        "valid_until": now + timedelta(days=30),
        "installation_id": "local-installation",
        "device_public_key": base64.b64encode(b"k" * 32).decode(),
        "key_id": "codivis-one-ed25519-1",
    }


def test_company_and_branch_trim_names_and_reject_blank_values():
    assert CompanyCreate(name="  Badulaque  ").name == "Badulaque"
    assert BranchCreate(name="  Central  ").name == "Central"
    with pytest.raises(ValidationError):
        CompanyCreate(name="   ")
    with pytest.raises(ValidationError):
        BranchCreate(name="   ")
    with pytest.raises(ValidationError):
        BranchUpdate()


def test_user_create_normalizes_email_and_requires_strong_password():
    user = UserCreate(email=" ADMIN@EMPRESA.COM ", password="Segura-1234!", password_confirmation="Segura-1234!")
    assert user.email == "admin@empresa.com"
    with pytest.raises(ValidationError):
        UserCreate(email="admin@empresa.com", password="simple", password_confirmation="simple")


def test_license_rejects_invalid_device_public_key():
    payload = license_payload()
    payload["device_public_key"] = "not-a-public-key"
    with pytest.raises(ValidationError):
        LicensePayload.model_validate(payload)
