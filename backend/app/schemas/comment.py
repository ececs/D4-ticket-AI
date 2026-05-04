import uuid
from datetime import datetime
from pydantic import BaseModel, Field, field_validator
from .user import UserOut


class CommentCreate(BaseModel):
    content: str = Field(..., min_length=1, max_length=5000)

    @field_validator("content")
    @classmethod
    def content_not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("content must not be blank")
        return v.strip()


class CommentOut(BaseModel):
    id: uuid.UUID
    ticket_id: uuid.UUID
    author_id: uuid.UUID
    content: str
    created_at: datetime
    author: UserOut | None = None

    model_config = {"from_attributes": True}
