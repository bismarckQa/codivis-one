from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.schemas.license import LicensePayload, SignedLicense


def valid_payload() -> dict:
    now = datetime.now(timezone.utc)
    return {
        "license_id": uuid4(),
        "company_name": "Empresa Demo",
        "edition": "base",
        "modules": ["dashboard"],
        "max_users": 5,
        "max_branches": 1,
        "created_at": now,
        "activation_expires_at": now + timedelta(minutes=30),
        "valid_from": now,
        "valid_until": now + timedelta(days=30),
        "installation_id": "local-installation",
        "device_public_key": "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=",
        "key_id": "codivis-one-ed25519-1",
    }


def test_license_payload_accepts_the_signed_license_contract():
    payload = LicensePayload.model_validate(valid_payload())

    assert payload.company_name == "Empresa Demo"
    assert payload.max_users == 5
    assert payload.modules == ["dashboard"]


@pytest.mark.parametrize("field", ["company_name", "installation_id", "key_id"])
def test_license_payload_rejects_empty_required_strings(field):
    data = valid_payload()
    data[field] = ""

    with pytest.raises(ValidationError):
        LicensePayload.model_validate(data)


def test_license_payload_rejects_expired_or_invalid_limits():
    data = valid_payload()
    data["valid_until"] = data["valid_from"]
    with pytest.raises(ValidationError):
        LicensePayload.model_validate(data)

    data = valid_payload()
    data["max_users"] = 0
    with pytest.raises(ValidationError):
        LicensePayload.model_validate(data)


def test_signed_license_requires_payload_and_signature():
    payload = valid_payload()
    signed = SignedLicense(payload=payload, signature="c2lnbmF0dXJl")

    assert signed.payload.license_id == payload["license_id"]

