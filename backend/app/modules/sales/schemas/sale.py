from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, computed_field, model_validator


def validate_money_storage(value: Decimal) -> None:
    if not value.is_finite() or value < 0 or value > Decimal("9999999999.9999"):
        raise ValueError("calculated amount exceeds Numeric(14, 4) storage")
    if value != value.quantize(Decimal("0.0001")):
        raise ValueError("calculated amount requires more than four decimal places")


class SaleItemCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    product_id: UUID
    quantity: Decimal = Field(gt=0, max_digits=14, decimal_places=4)
    unit_price: Decimal = Field(ge=0, max_digits=14, decimal_places=4)

    @model_validator(mode="after")
    def validate_line_storage(self):
        validate_money_storage(self.line_total)
        return self

    @computed_field
    @property
    def line_total(self) -> Decimal:
        return self.quantity * self.unit_price


class SaleCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    branch_id: UUID
    items: list[SaleItemCreate] = Field(min_length=1)
    discount: Decimal = Field(default=0, ge=0, max_digits=14, decimal_places=4)
    tax: Decimal = Field(default=0, ge=0, max_digits=14, decimal_places=4)
    notes: str | None = Field(default=None, max_length=5000)

    @model_validator(mode="after")
    def validate_lines_and_discount(self):
        product_ids = [item.product_id for item in self.items]
        if len(product_ids) != len(set(product_ids)):
            raise ValueError("each product can appear only once in a sale")
        if self.discount > sum((item.line_total for item in self.items), Decimal("0")):
            raise ValueError("discount cannot exceed the subtotal")
        validate_money_storage(self.subtotal)
        validate_money_storage(self.total)
        return self

    @computed_field
    @property
    def subtotal(self) -> Decimal:
        return sum((item.line_total for item in self.items), Decimal("0"))

    @computed_field
    @property
    def total(self) -> Decimal:
        return self.subtotal - self.discount + self.tax


class SaleItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    product_id: UUID
    quantity: Decimal
    unit_price: Decimal
    line_total: Decimal


class SaleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    branch_id: UUID
    status: str
    subtotal: Decimal
    discount: Decimal
    tax: Decimal
    total: Decimal
    notes: str | None
    confirmed_at: datetime | None
    items: list[SaleItemResponse]
