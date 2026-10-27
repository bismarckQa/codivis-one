from datetime import datetime, timedelta, timezone
import base64
import json
from pathlib import Path
from uuid import uuid4

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from fastapi import HTTPException

from app.core.config import Settings
from app.core.security import ClockRollbackDetected, canonical, check_clock_state, ensure_activation_identity, load_json_no_duplicates
from app.models.license import License
from app.services.license_service import validate_signed_license, verify_stored_license


def signed_document(tmp_path: Path, *, expires_in_hours: int = 1, activation_expires_minutes: int = 30, product: str | None = None):
    now = datetime.now(timezone.utc).replace(microsecond=0)
    payload = {
        "license_id": str(uuid4()),
        "company_name": "Empresa Demo",
        "edition": "base",
        "modules": ["dashboard"],
        "max_users": 5,
        "max_branches": 1,
        "created_at": now.isoformat(),
        "activation_expires_at": (now + timedelta(minutes=activation_expires_minutes)).isoformat(),
        "valid_from": now.isoformat(),
        "valid_until": (now + timedelta(hours=expires_in_hours)).isoformat(),
        "installation_id": "local-installation",
        "key_id": "codivis-one-ed25519-1",
    }
    if product is not None:
        payload["product"] = product
    private = Ed25519PrivateKey.generate()
    payload["device_public_key"] = base64.b64encode(private.public_key().public_bytes_raw()).decode()
    public_path = tmp_path / "public.key"
    public_path.write_bytes(private.public_key().public_bytes_raw())
    document = {"payload": payload, "signature": base64.b64encode(private.sign(canonical(payload))).decode()}
    settings = Settings("postgresql+psycopg://unused", b"0" * 32, b"pepper", public_path)
    return document, settings


def test_import_verifies_the_signed_document(tmp_path):
    document, settings = signed_document(tmp_path)

    payload, raw_payload, signature = validate_signed_license(document, settings)

    assert str(payload.license_id) == raw_payload["license_id"]
    assert signature == document["signature"]


def test_tampered_payload_is_rejected(tmp_path):
    document, settings = signed_document(tmp_path)
    document["payload"]["max_users"] = 999

    with pytest.raises(HTTPException):
        validate_signed_license(document, settings)


def test_license_for_another_product_is_rejected(tmp_path):
    document, settings = signed_document(tmp_path, product="otro-producto")

    with pytest.raises(HTTPException):
        validate_signed_license(document, settings)


def test_activation_file_expired_before_import_is_rejected(tmp_path):
    document, settings = signed_document(tmp_path, activation_expires_minutes=-1)

    with pytest.raises(HTTPException):
        validate_signed_license(document, settings)


def test_license_is_bound_to_the_local_device_key(tmp_path):
    document, settings = signed_document(tmp_path)
    assert validate_signed_license(document, settings)[0].device_public_key


def test_runtime_verification_rejects_a_database_row_without_signature(tmp_path):
    document, settings = signed_document(tmp_path)
    payload, _raw, _signature = validate_signed_license(document, settings)
    license_row = License(
        id=payload.license_id,
        company_id=uuid4(),
        edition=payload.edition,
        max_users=payload.max_users,
        max_branches=payload.max_branches,
        modules=payload.modules,
        valid_from=payload.valid_from,
        valid_until=payload.valid_until,
        installation_id=payload.installation_id,
        key_id=payload.key_id,
        signed_payload=None,
        signature=None,
    )

    with pytest.raises(ValueError):
        verify_stored_license(license_row, settings)


def test_runtime_verification_rejects_expiry_changed_directly_in_database(tmp_path):
    document, settings = signed_document(tmp_path)
    payload, raw_payload, signature = validate_signed_license(document, settings)
    license_row = License(
        id=payload.license_id,
        company_id=uuid4(),
        edition=payload.edition,
        max_users=payload.max_users,
        max_branches=payload.max_branches,
        modules=payload.modules,
        valid_from=payload.valid_from,
        valid_until=datetime(2036, 1, 1, tzinfo=timezone.utc),
        installation_id=payload.installation_id,
        key_id=payload.key_id,
        signed_payload=raw_payload,
        signature=signature,
    )

    with pytest.raises(ValueError):
        verify_stored_license(license_row, settings)


def test_json_loader_rejects_duplicate_keys():
    with pytest.raises(ValueError):
        load_json_no_duplicates('{"payload": {}, "payload": {}}')


def test_activation_identity_persists_across_requests(tmp_path):
    private_path = tmp_path / "device.key"
    first_key, first_installation = ensure_activation_identity(private_path)
    second_key, second_installation = ensure_activation_identity(private_path)

    assert first_installation == second_installation
    assert first_key.private_bytes_raw() == second_key.private_bytes_raw()


def test_clock_rollback_is_detected(tmp_path):
    state = tmp_path / "clock.json"
    check_clock_state(state, datetime(2026, 1, 2, tzinfo=timezone.utc))
    with pytest.raises(ClockRollbackDetected):
        check_clock_state(state, datetime(2026, 1, 1, tzinfo=timezone.utc))

