from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator

from app.modules.core.schemas.common import normalized_email, strong_password


class UserCreate(BaseModel):
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


class UserResponse(BaseModel):
    id: str
    email: EmailStr
    is_admin: bool
    is_active: bool
