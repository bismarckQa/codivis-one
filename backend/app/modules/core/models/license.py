from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, Text, func
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.modules.core.models.base import Base


class License(Base):
    __tablename__ = "licenses"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    company_id: Mapped[UUID] = mapped_column(ForeignKey("companies.id"), nullable=False)
    edition: Mapped[str] = mapped_column(String, nullable=False)
    max_users: Mapped[int] = mapped_column(Integer, nullable=False)
    max_branches: Mapped[int] = mapped_column(Integer, nullable=False)
    modules: Mapped[list[Any]] = mapped_column(JSON, nullable=False, default=list)
    valid_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    valid_until: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    installation_id: Mapped[str] = mapped_column(String, nullable=False)
    key_id: Mapped[str] = mapped_column(String, nullable=False)
    signed_payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    signature: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    company = relationship("Company", back_populates="licenses")
    tokens = relationship("LicenseToken", back_populates="license")
