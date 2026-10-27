from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, LargeBinary, func
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.modules.core.models.base import Base


class Company(Base):
    __tablename__ = "companies"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    name_ciphertext: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    name_fingerprint: Mapped[bytes] = mapped_column(LargeBinary, nullable=False, unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    licenses = relationship("License", back_populates="company")
    users = relationship("User", back_populates="company")
    branches = relationship("Branch", back_populates="company")
    customers = relationship("Customer", back_populates="company")
    products = relationship("Product", back_populates="company")
