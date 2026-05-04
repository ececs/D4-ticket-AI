import uuid
from datetime import datetime
from pydantic import BaseModel

from app.schemas.user import UserOut


class TicketHistoryOut(BaseModel):
    id: uuid.UUID
    ticket_id: uuid.UUID | None
    actor: UserOut | None = None
    field: str
    old_value: str | None
    new_value: str | None
    created_at: datetime

    model_config = {"from_attributes": True}
