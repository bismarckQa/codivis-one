from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.modules.core.schemas.common import normalized_text


class ProductCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=255)
    price: Decimal = Field(default=Decimal("0"), ge=0, max_digits=14, decimal_places=4)
    cost: Decimal = Field(default=Decimal("0"), ge=0, max_digits=14, decimal_places=4)

    @field_validator("code", mode="before")
    @classmethod
    def normalize_code(cls, value: str) -> str:
        return normalized_text(value).upper()

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        return normalized_text(value)


class ProductUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str | None = Field(default=None, min_length=1, max_length=100)
    name: str | None = Field(default=None, min_length=1, max_length=255)
    price: Decimal | None = Field(default=None, ge=0, max_digits=14, decimal_places=4)
    cost: Decimal | None = Field(default=None, ge=0, max_digits=14, decimal_places=4)
    is_active: bool | None = None

    @field_validator("code", mode="before")
    @classmethod
    def normalize_code(cls, value: str | None) -> str | None:
        return normalized_text(value).upper() if value is not None else value

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str | None) -> str | None:
        return normalized_text(value) if value is not None else value

    @model_validator(mode="after")
    def require_change(self):
        values = self.model_dump(exclude_unset=True)
        if not values:
            raise ValueError("at least one product field is required")
        if any(value is None for value in values.values()):
            raise ValueError("product update fields cannot be null")
        return self


class ProductResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    code: str
    name: str
    price: Decimal
    cost: Decimal
    is_active: bool
    created_at: datetime
    updated_at: datetime
