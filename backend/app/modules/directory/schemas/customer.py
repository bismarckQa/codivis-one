from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

from app.schemas.common import normalized_email, normalized_text


class CustomerCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=255)
    tax_id: str | None = Field(default=None, max_length=64)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=64)
    notes: str | None = Field(default=None, max_length=5000)

    @field_validator("name", mode="before")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        return normalized_text(value)

    @field_validator("tax_id", "phone", "notes", mode="before")
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        return None if value is None or not str(value).strip() else " ".join(str(value).split())

    @field_validator("email", mode="before")
    @classmethod
    def normalize_customer_email(cls, value: str | None) -> str | None:
        return None if value is None or not str(value).strip() else normalized_email(value)


class CustomerUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=255)
    tax_id: str | None = Field(default=None, max_length=64)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=64)
    notes: str | None = Field(default=None, max_length=5000)
    is_active: bool | None = None

    @field_validator("name", mode="before")
    @classmethod
    def normalize_name(cls, value: str | None) -> str | None:
        return None if value is None else normalized_text(value)

    @field_validator("tax_id", "phone", "notes", mode="before")
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        return None if value is None or not str(value).strip() else " ".join(str(value).split())

    @field_validator("email", mode="before")
    @classmethod
    def normalize_customer_email(cls, value: str | None) -> str | None:
        return None if value is None or not str(value).strip() else normalized_email(value)

    @model_validator(mode="after")
    def require_change(self):
        if not self.model_fields_set:
            raise ValueError("at least one customer field is required")
        for field in ("name", "is_active"):
            if field in self.model_fields_set and getattr(self, field) is None:
                raise ValueError(f"{field} cannot be null")
        return self


class CustomerResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    tax_id: str | None
    email: EmailStr | None
    phone: str | None
    notes: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime
