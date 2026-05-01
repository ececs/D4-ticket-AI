import uuid
from datetime import datetime
from pydantic import BaseModel
from app.models.notification import NotificationType


class NotificationOut(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    type: NotificationType
    ticket_id: uuid.UUID
    message: str
    read: bool
    created_at: datetime

    model_config = {"from_attributes": True}
