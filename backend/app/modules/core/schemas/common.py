import base64
import re
from typing import Any


def normalized_text(value: Any) -> str:
    if not isinstance(value, str):
        raise ValueError("must be text")
    value = " ".join(value.split())
    if not value:
        raise ValueError("must not be blank")
    return value


def normalized_email(value: Any) -> str:
    if not isinstance(value, str):
        raise ValueError("email must be text")
    return value.strip().lower()


def strong_password(value: str) -> str:
    checks = (r"[a-z]", r"[A-Z]", r"\d", r"[^A-Za-z0-9]")
    if len(value) < 12 or not all(re.search(pattern, value) for pattern in checks):
        raise ValueError("password must contain 12 characters, upper, lower, number and symbol")
    return value


def ed25519_public_key(value: str) -> str:
    try:
        decoded = base64.b64decode(value, validate=True)
    except (ValueError, TypeError):
        raise ValueError("device_public_key must be valid base64")
    if len(decoded) != 32:
        raise ValueError("device_public_key must contain 32 bytes")
    return value

__all__ = ["ed25519_public_key", "normalized_email", "normalized_text", "strong_password"]
