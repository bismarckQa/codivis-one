from __future__ import annotations

import base64
import secrets
import sys
from pathlib import Path


def value_or_generated(current: str | None, generated: str) -> str:
    if not current or current.startswith("REPLACE_WITH_"):
        return generated
    return current


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    env_path = root / ".env"
    example_path = root / ".env.example"
    values: dict[str, str] = {}
    original_lines: list[str] = []
    if env_path.exists():
        original_lines = env_path.read_text().splitlines()
        for line in original_lines:
            if "=" in line and not line.lstrip().startswith("#"):
                key, value = line.split("=", 1)
                values[key] = value
    elif example_path.exists():
        for line in example_path.read_text().splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                key, value = line.split("=", 1)
                values[key] = value

    try:
        from cryptography.fernet import Fernet
    except ImportError as exc:
        raise SystemExit("Dependencias no instaladas: ejecuta primero setup-dev.") from exc

    values["POSTGRES_PASSWORD"] = value_or_generated(values.get("POSTGRES_PASSWORD"), secrets.token_urlsafe(32))
    values["APP_ENCRYPTION_KEY"] = value_or_generated(values.get("APP_ENCRYPTION_KEY"), Fernet.generate_key().decode())
    values["TOKEN_PEPPER"] = value_or_generated(values.get("TOKEN_PEPPER"), base64.urlsafe_b64encode(secrets.token_bytes(32)).decode())
    values["ISSUER_ADMIN_TOKEN"] = value_or_generated(values.get("ISSUER_ADMIN_TOKEN"), secrets.token_urlsafe(48))
    values["LICENSE_PUBLIC_KEY_FILE"] = values.get("LICENSE_PUBLIC_KEY_FILE") or "./license-issuer/data/public/codivis-one-ed25519.pub"
    values["DATABASE_URL"] = f"postgresql://{values.get('POSTGRES_USER', 'codivis_one')}:{values['POSTGRES_PASSWORD']}@codivis-one-postgres:5432/{values.get('POSTGRES_DB', 'codivis_one')}"

    ordered = [
        "POSTGRES_DB", "POSTGRES_USER", "POSTGRES_PASSWORD", "POSTGRES_PORT",
        "DATABASE_URL", "APP_ENCRYPTION_KEY", "TOKEN_PEPPER", "LICENSE_PUBLIC_KEY_FILE", "ISSUER_ADMIN_TOKEN",
    ]
    rendered: list[str] = []
    written: set[str] = set()
    for line in original_lines:
        if "=" not in line or line.lstrip().startswith("#"):
            rendered.append(line)
            continue
        key = line.split("=", 1)[0]
        if key in values:
            rendered.append(f"{key}={values[key]}")
            written.add(key)
        else:
            rendered.append(line)
    for key in ordered:
        if key not in written and not any(line.startswith(f"{key}=") for line in rendered):
            rendered.append(f"{key}={values.get(key, '')}")
    env_path.write_text("\n".join(rendered) + "\n")
    print(f"Configuración preparada en {env_path}")


if __name__ == "__main__":
    main()
