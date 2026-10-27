from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, LargeBinary, String, func
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.modules.core.models.base import Base


class LicenseToken(Base):
    __tablename__ = "license_tokens"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    license_id: Mapped[UUID] = mapped_column(ForeignKey("licenses.id"), nullable=False)
    user_id: Mapped[Optional[UUID]] = mapped_column(ForeignKey("users.id"))
    token_type: Mapped[str] = mapped_column(String, nullable=False)
    token_hash: Mapped[bytes] = mapped_column(LargeBinary, nullable=False, unique=True)
    company_fingerprint: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    company_name_ciphertext: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    license_payload_ciphertext: Mapped[Optional[bytes]] = mapped_column(LargeBinary)
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    last_used_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    license = relationship("License", back_populates="tokens")
    user = relationship("User", back_populates="tokens")
