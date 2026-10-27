from pydantic import BaseModel, EmailStr, field_validator

from app.modules.core.schemas.user import UserCreate
from app.modules.core.schemas.common import normalized_email


class BootstrapRequest(UserCreate):
    activation_token: str | None = None


class LoginRequest(BaseModel):
    email: EmailStr
    password: str

    @field_validator("email", mode="before")
    @classmethod
    def normalize_login_email(cls, value: str) -> str:
        return normalized_email(value)


class AuthResponse(BaseModel):
    status: str
