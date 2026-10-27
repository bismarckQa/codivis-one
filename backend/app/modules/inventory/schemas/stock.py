from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.modules.inventory.models.stock import MovementType


class StockBalanceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    branch_id: UUID
    product_id: UUID
    quantity: Decimal


class StockMovementResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    branch_id: UUID
    product_id: UUID
    movement_type: MovementType
    quantity: Decimal
    reference_type: str
    reference_id: UUID
    reason: str | None
    created_at: datetime
