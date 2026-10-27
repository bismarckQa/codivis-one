from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator


AdjustmentReason = Literal["merma", "vencimiento", "danio", "devolucion_proveedor", "correccion"]


class StockAdjustmentItemCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    product_id: UUID
    quantity: Decimal = Field(gt=0, max_digits=14, decimal_places=4)


class StockAdjustmentCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    branch_id: UUID
    reason: AdjustmentReason
    notes: str | None = Field(default=None, max_length=5000)
    items: list[StockAdjustmentItemCreate] = Field(min_length=1)

    @model_validator(mode="after")
    def unique_products(self):
        ids = [item.product_id for item in self.items]
        if len(ids) != len(set(ids)):
            raise ValueError("each product can appear only once in an adjustment")
        return self


class StockAdjustmentItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    product_id: UUID
    quantity: Decimal


class StockAdjustmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    branch_id: UUID
    status: str
    reason: str
    notes: str | None
    created_at: datetime
    confirmed_at: datetime | None
    items: list[StockAdjustmentItemResponse]


class StockReceiptItemCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    product_id: UUID
    quantity: Decimal = Field(gt=0, max_digits=14, decimal_places=4)


class StockReceiptCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    operation_id: UUID = Field(default_factory=uuid4)
    branch_id: UUID
    notes: str | None = Field(default=None, max_length=5000)
    items: list[StockReceiptItemCreate] = Field(min_length=1)

    @model_validator(mode="after")
    def unique_products(self):
        ids = [item.product_id for item in self.items]
        if len(ids) != len(set(ids)):
            raise ValueError("each product can appear only once in a receipt")
        return self


class StockReceiptResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    operation_id: UUID
    branch_id: UUID
    items: list[StockReceiptItemCreate]
