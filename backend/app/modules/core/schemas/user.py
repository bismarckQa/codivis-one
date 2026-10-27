from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

from app.modules.core.schemas.common import normalized_email, strong_password


class UserCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: EmailStr
    password: str = Field(min_length=12, max_length=128)
    password_confirmation: str = Field(min_length=12, max_length=128)

    @field_validator("email", mode="before")
    @classmethod
    def normalize_user_email(cls, value: str) -> str:
        return normalized_email(value)

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: str) -> str:
        return strong_password(value)

    @model_validator(mode="after")
    def passwords_match(self):
        if self.password != self.password_confirmation:
            raise ValueError("passwords do not match")
        return self


class UserUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: EmailStr | None = None
    password: str | None = Field(default=None, min_length=12, max_length=128)
    password_confirmation: str | None = Field(default=None, min_length=12, max_length=128)
    is_admin: bool | None = None
    is_active: bool | None = None

    @field_validator("email", mode="before")
    @classmethod
    def normalize_user_email(cls, value: str | None) -> str | None:
        return normalized_email(value) if value is not None else value

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: str | None) -> str | None:
        return strong_password(value) if value is not None else value

    @model_validator(mode="after")
    def validate_changes(self):
        values = self.model_dump(exclude_unset=True)
        if not values:
            raise ValueError("at least one user field is required")
        if any(value is None for value in values.values()):
            raise ValueError("user update fields cannot be null")
        password_fields = {"password", "password_confirmation"}
        present_password_fields = password_fields.intersection(values)
        if present_password_fields and present_password_fields != password_fields:
            raise ValueError("password and password_confirmation must be provided together")
        if self.password is not None and self.password != self.password_confirmation:
            raise ValueError("passwords do not match")
        return self


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: EmailStr
    is_admin: bool
    is_active: bool
