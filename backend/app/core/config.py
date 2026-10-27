from dataclasses import dataclass
import os
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    database_url: str
    app_encryption_key: bytes
    token_pepper: bytes
    license_public_key_path: Path
    license_public_key_sha256: str | None = None
    activation_private_key_path: Path = Path("/data/activation/codivis-one-device.key")
    clock_state_path: Path | None = None

    @classmethod
    def from_env(cls) -> "Settings":
        database_url = os.environ["DATABASE_URL"]
        if database_url.startswith("postgresql://"):
            database_url = database_url.replace("postgresql://", "postgresql+psycopg://", 1)
        return cls(
            database_url=database_url,
            app_encryption_key=os.environ["APP_ENCRYPTION_KEY"].encode(),
            token_pepper=os.environ["TOKEN_PEPPER"].encode(),
            license_public_key_path=Path(os.getenv("LICENSE_PUBLIC_KEY_PATH", "/run/license-public/codivis-one-ed25519.pub")),
            license_public_key_sha256=os.getenv("LICENSE_PUBLIC_KEY_SHA256") or None,
            activation_private_key_path=Path(os.getenv("ACTIVATION_PRIVATE_KEY_PATH", "/data/activation/codivis-one-device.key")),
            clock_state_path=Path(os.getenv("CLOCK_STATE_PATH", "/data/activation/codivis-one-clock.json")),
        )
