from pydantic import BaseModel, Field, field_validator

from app.modules.core.schemas.common import normalized_text


class CompanyCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)

    @field_validator("name", mode="before")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        return normalized_text(value)


class CompanyResponse(BaseModel):
    id: str
    name: str
