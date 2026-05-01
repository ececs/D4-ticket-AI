import uuid
from datetime import datetime
from pydantic import BaseModel
from app.models.ticket import TicketStatus, TicketPriority
from .user import UserOut


class TicketCreate(BaseModel):
    title: str
    description: str | None = None
    priority: TicketPriority = TicketPriority.medium
    assignee_id: uuid.UUID | None = None


class TicketUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    status: TicketStatus | None = None
    priority: TicketPriority | None = None
    assignee_id: uuid.UUID | None = None


class TicketOut(BaseModel):
    id: uuid.UUID
    title: str
    description: str | None
    status: TicketStatus
    priority: TicketPriority
    author_id: uuid.UUID
    assignee_id: uuid.UUID | None
    created_at: datetime
    updated_at: datetime
    author: UserOut | None = None
    assignee: UserOut | None = None

    model_config = {"from_attributes": True}


class TicketListResponse(BaseModel):
    items: list[TicketOut]
    total: int
    page: int
    size: int
