from enum import Enum
from typing import Any, Dict, Optional
from pydantic import BaseModel, ConfigDict, Field
import uuid

class WSMessageType(str, Enum):
    NOTIFICATION = "notification"
    WEB_SCRAPE_COMPLETED = "web_scrape_completed"
    TICKET_UPDATED = "ticket_updated"
    SYSTEM_ALERT = "system_alert"

class WSMessage(BaseModel):
    """
    Standard envelope for all WebSocket messages.
    """
    type: WSMessageType
    ticket_id: Optional[uuid.UUID] = None
    data: Dict[str, Any] = Field(default_factory=dict)
    message: Optional[str] = None

    model_config = ConfigDict(use_enum_values=True, populate_by_name=True)
