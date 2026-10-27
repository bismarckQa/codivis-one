import base64
import hashlib
import hmac
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from argon2 import PasswordHasher
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from cryptography.hazmat.primitives.serialization import Encoding, PrivateFormat, PublicFormat, NoEncryption

from app.core.config import Settings


passwords = PasswordHasher()


class ClockRollbackDetected(ValueError):
    pass


def check_clock_state(path: Path, now: datetime | None = None, tolerance_seconds: int = 300) -> None:
    current = now or datetime.now(timezone.utc)
    last_seen: datetime | None = None
    if path.exists():
        try:
            last_seen = datetime.fromisoformat(json.loads(path.read_text(encoding="utf-8"))["last_seen"])
        except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise ClockRollbackDetected("clock state is invalid") from exc
    if last_seen and current < last_seen - timedelta(seconds=tolerance_seconds):
        raise ClockRollbackDetected("system clock moved backwards")
    if last_seen is None or current > last_seen:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(json.dumps({"last_seen": current.isoformat()}) + "\n", encoding="utf-8")
        temporary.chmod(0o600)
        temporary.replace(path)


def ensure_activation_key(path: Path) -> Ed25519PrivateKey:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_bytes(Ed25519PrivateKey.generate().private_bytes(Encoding.Raw, PrivateFormat.Raw, NoEncryption()))
        path.chmod(0o600)
    return Ed25519PrivateKey.from_private_bytes(path.read_bytes())


def ensure_activation_identity(path: Path, initial_installation_id: str | None = None) -> tuple[Ed25519PrivateKey, str]:
    """Load the device key and stable installation id, creating each once."""
    key = ensure_activation_key(path)
    identity_path = path.with_suffix(".json")
    if identity_path.exists():
        try:
            document = json.loads(identity_path.read_text(encoding="utf-8"))
            installation_id = str(document["installation_id"])
            from uuid import UUID

            UUID(installation_id)
        except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise RuntimeError("device identity file is invalid; refusing to regenerate it") from exc
    else:
        installation_id = initial_installation_id or str(uuid4())
        from uuid import UUID

        UUID(installation_id)
        identity_path.write_text(json.dumps({"installation_id": installation_id}) + "\n", encoding="utf-8")
        identity_path.chmod(0o600)
    return key, installation_id


def activation_public_key(path: Path) -> str:
    key, _installation_id = ensure_activation_identity(path)
    return base64.b64encode(key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)).decode()


def activation_request(path: Path, initial_installation_id: str | None = None) -> dict[str, Any]:
    key, installation_id = ensure_activation_identity(path, initial_installation_id)
    document: dict[str, Any] = {
        "request_type": "codivis-one-activation-request-v2",
        "schema_version": 2,
        "request_id": str(uuid4()),
        "created_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "installation_id": installation_id,
        "device_public_key": base64.b64encode(key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)).decode(),
    }
    document["request_signature"] = base64.b64encode(key.sign(canonical(document))).decode()
    return document


def activation_key_matches(encoded_public_key: str, path: Path) -> bool:
    try:
        expected = base64.b64decode(encoded_public_key, validate=True)
        actual = ensure_activation_key(path).public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
        return hmac.compare_digest(expected, actual)
    except (ValueError, TypeError):
        return False


def digest(value: str, pepper: bytes) -> bytes:
    return hmac.new(pepper, value.encode(), hashlib.sha256).digest()


def canonical(payload: dict[str, Any]) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def load_json_no_duplicates(value: str) -> dict[str, Any]:
    def reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, item in pairs:
            if key in result:
                raise ValueError("duplicate JSON key")
            result[key] = item
        return result

    parsed = json.loads(value, object_pairs_hook=reject_duplicates)
    if not isinstance(parsed, dict):
        raise ValueError("JSON document must be an object")
    return parsed


def encrypt(value: str, settings: Settings) -> bytes:
    return Fernet(settings.app_encryption_key).encrypt(value.encode())


def decrypt(value: bytes, settings: Settings) -> str:
    return Fernet(settings.app_encryption_key).decrypt(value).decode()


def verify_signature(payload: dict[str, Any], encoded_signature: str, public_key_path: Path, expected_sha256: str | None = None) -> None:
    signature = base64.b64decode(encoded_signature, validate=True)
    public_bytes = public_key_path.read_bytes()
    if expected_sha256 and not hmac.compare_digest(hashlib.sha256(public_bytes).hexdigest(), expected_sha256.lower()):
        raise ValueError("license public key fingerprint mismatch")
    public = Ed25519PublicKey.from_public_bytes(public_bytes)
    public.verify(signature, canonical(payload))
