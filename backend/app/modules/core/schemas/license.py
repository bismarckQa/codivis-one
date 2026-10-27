from datetime import datetime, timezone
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.modules.core.schemas.common import ed25519_public_key


class LicensePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    product: str = "codivis-one"
    schema_version: int = 1
    activation_request_id: UUID | None = None
    license_id: UUID
    company_name: str = Field(min_length=1, max_length=255)
    edition: str = Field(min_length=1, max_length=32)
    modules: list[str] = Field(default_factory=list)
    max_users: int = Field(ge=1)
    max_branches: int = Field(ge=1)
    created_at: datetime
    activation_expires_at: datetime
    valid_from: datetime
    valid_until: datetime
    installation_id: str = Field(min_length=1, max_length=255)
    device_public_key: str = Field(min_length=43, max_length=64)
    key_id: str = Field(min_length=1, max_length=128)

    @field_validator("company_name", "edition", "installation_id", "key_id")
    @classmethod
    def non_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("must not be blank")
        return value.strip()

    @field_validator("product")
    @classmethod
    def supported_product(cls, value: str) -> str:
        if value != "codivis-one":
            raise ValueError("unsupported product")
        return value

    @field_validator("device_public_key")
    @classmethod
    def validate_device_key(cls, value: str) -> str:
        return ed25519_public_key(value)

    @model_validator(mode="after")
    def valid_window(self):
        if self.activation_expires_at <= self.created_at:
            raise ValueError("activation_expires_at must be after created_at")
        if self.valid_until <= self.valid_from:
            raise ValueError("valid_until must be after valid_from")
        if any(value.tzinfo is None for value in (self.created_at, self.activation_expires_at, self.valid_from, self.valid_until)):
            raise ValueError("license timestamps must include timezone")
        return self


class SignedLicense(BaseModel):
    model_config = ConfigDict(extra="forbid")
    payload: LicensePayload
    signature: str = Field(min_length=1)


class LicenseStatus(BaseModel):
    licensed: bool
    status: str
    renewal_required: bool
    server_date: datetime
    seconds_remaining: int
    days_remaining: int
    company_name: str | None = None
    created_at: datetime | None = None
    valid_until: datetime | None = None
    edition: str | None = None
    max_users: int | None = None
    max_branches: int | None = None
    modules: list[str] = Field(default_factory=list)
    admin_created: bool = False
