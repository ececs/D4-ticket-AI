import uuid
from datetime import datetime
from pydantic import BaseModel
from .user import UserOut


class CommentCreate(BaseModel):
    content: str


class CommentOut(BaseModel):
    id: uuid.UUID
    ticket_id: uuid.UUID
    author_id: uuid.UUID
    content: str
    created_at: datetime
    author: UserOut | None = None

    model_config = {"from_attributes": True}
