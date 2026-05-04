"""
AI Router - FastAPI Endpoints for Chat and Assistant Logic.

This module handles the HTTP interface for the AI agent, providing:
- Persistent chat memory via PostgreSQL checkpointers.
- Real-time streaming responses via SSE (Server-Sent Events).
- Model prefix transparency (Gemini: / GPT:).
- Tool execution visibility (green chips in the UI).
"""

import json
import logging
import uuid
from typing import List, Optional
from pydantic import BaseModel

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from langchain_core.messages import HumanMessage, AIMessage

from app.ai.agent import build_agent
from app.core.dependencies import get_current_user
from app.db.session import get_db
from app.models.user import User
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/ai", tags=["AI"])

class ChatRequest(BaseModel):
    message: Optional[str] = None
    messages: List[dict] = []  # Added to support history from frontend
    thread_id: Optional[str] = None
    selected_ticket_ids: List[str] = [] # Renamed to match frontend
    current_ticket_id: Optional[str] = None

@router.post("/chat")
async def chat_endpoint(
    request: ChatRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Main entry point for the AI assistant.
    Supports persistent threads and streams the response via SSE.
    """
    # Extract the actual user message from the request
    user_text = request.message
    if not user_text and request.messages:
        # Take the content of the last user message in the list
        last_msg = request.messages[-1]
        user_text = last_msg.get("content", "")
    
    user_text = user_text or ""
    thread_id = request.thread_id or str(uuid.uuid4())
    
    # Context injection: telling the agent who the user is and the current time.
    from datetime import datetime
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    context_msg = f"\n\n[SYSTEM CONTEXT]\nUser: {current_user.display_name} ({current_user.email})\nCurrent Time: {now}\n"
    if request.current_ticket_id:
        context_msg += f"USER IS CURRENTLY VIEWING TICKET ID: {request.current_ticket_id}\n"
    if request.selected_ticket_ids:
        context_msg += f"USER HAS SELECTED THESE TICKETS: {', '.join(request.selected_ticket_ids)}\n"
    
    initial_state = {"messages": [HumanMessage(content=user_text)]}
    config = {"configurable": {"thread_id": thread_id}}

    async def event_stream():
        v_logger = logging.getLogger("uvicorn.error")
        v_logger.info("AI Session: thread_id=%s", thread_id)

        try:
            # build_agent needs the current session and the current user (actor)
            agent = build_agent(db, current_user, context_msg)
            if not agent:
                yield f"data: {json.dumps({'type': 'error', 'content': 'AI agent not initialized'})}\n\n"
                return

            # Send thread_id back to frontend for persistence
            yield f"data: {json.dumps({'type': 'session', 'thread_id': thread_id})}\n\n"

            # Define the stream processing logic in a separate generator to allow retries
            async def process_events():
                has_content = False
                active_model = "IA"
                
                async for event in agent.astream_events(initial_state, version="v2", config=config):
                    kind = event["event"]

                    if kind == "on_chat_model_start":
                        m_name = event.get("name", "")
                        active_model = "Gemini" if "Google" in m_name else "GPT" if "OpenAI" in m_name else "IA"
                    
                    elif kind == "on_chat_model_stream":
                        chunk = event["data"]["chunk"]
                        if chunk and hasattr(chunk, "content") and chunk.content:
                            content = chunk.content
                            if not has_content:
                                content = f"{active_model}: " + content
                                has_content = True
                            yield f"data: {json.dumps({'type': 'token', 'content': content})}\n\n"

                    elif kind == "on_tool_start":
                        yield f"data: {json.dumps({'type': 'tool_start', 'name': event.get('name', '')})}\n\n"

                    elif kind == "on_tool_end":
                        tool_name = event.get("name", "")
                        raw_output = event.get("data", {}).get("output", "")
                        tool_output = str(raw_output.content) if hasattr(raw_output, "content") else str(raw_output)
                        
                        # Intercept the delete marker — never show it as raw text to the user
                        if tool_output.startswith("__DELETE_REQUESTED__:"):
                            parts = tool_output.split(":", 2)
                            t_id = parts[1] if len(parts) > 1 else ""
                            t_title = parts[2] if len(parts) > 2 else "this ticket"
                            yield f"data: {json.dumps({'type': 'confirmation_required', 'ticket_id': t_id, 'ticket_title': t_title})}\n\n"
                        else:
                            yield f"data: {json.dumps({'type': 'tool_call', 'name': tool_name, 'result': tool_output})}\n\n"

            # Auto-recovery wrapper for corrupted LangGraph sessions
            try:
                async for chunk in process_events():
                    yield chunk
            except ValueError as e:
                if "INVALID_CHAT_HISTORY" in str(e):
                    v_logger.warning("Corrupted history for thread %s. Resetting...", thread_id)
                    await agent.aupdate_state(config, {"messages": []})
                    async for chunk in process_events():
                        yield chunk
                else:
                    raise

            yield f"data: {json.dumps({'type': 'done'})}\n\n"

        except Exception as e:
            v_logger.error("Chat Stream Error: %s", str(e), exc_info=True)
            yield f"data: {json.dumps({'type': 'error', 'content': str(e)})}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
    )
