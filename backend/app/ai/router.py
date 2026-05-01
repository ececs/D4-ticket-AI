"""
AI chat router — POST /ai/chat with Server-Sent Events streaming.

Endpoint: POST /api/v1/ai/chat
Request body: { "messages": [{"role": "user"|"assistant", "content": "..."}] }
Response: text/event-stream (SSE)

SSE stream format:
  data: {"type": "token", "content": "..."}\n\n   — incremental text token
  data: {"type": "tool_call", "name": "...", "result": "..."}\n\n  — tool execution
  data: {"type": "done"}\n\n   — signals end of stream

Why SSE instead of WebSocket for the AI?
  SSE is simpler for request-response streaming: one HTTP POST → one stream of events.
  WebSockets add bidirectional complexity that isn't needed here — the user sends one
  message and receives a streamed response.

  The notification WebSocket is kept separate (it's a long-lived persistent connection).

Streaming with LangGraph:
  agent.astream_events() yields LangChain events as the agent runs.
  We filter for on_chat_model_stream (text tokens) and on_tool_end (tool results)
  and forward them to the SSE stream. Other internal events are discarded.
"""

import json

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.core.dependencies import CurrentUser, DB
from app.ai.agent import build_agent

router = APIRouter(prefix="/ai", tags=["AI Agent"])


class ChatMessage(BaseModel):
    role: str   # "user" | "assistant"
    content: str


class ChatRequest(BaseModel):
    messages: list[ChatMessage]


@router.post("/chat")
async def chat(
    request: ChatRequest,
    db: DB,
    current_user: CurrentUser,
):
    """
    Stream an AI response to a chat conversation.

    The full conversation history is passed on each request (stateless backend).
    The frontend maintains the message list and appends new messages before each call.

    Returns a Server-Sent Events stream. The stream ends with {"type": "done"}.
    """
    agent = build_agent(db, current_user)

    # Convert API message format to LangChain message format
    lc_messages = [
        {"role": msg.role, "content": msg.content}
        for msg in request.messages
    ]

    async def event_stream():
        """
        Generator that yields SSE-formatted strings from the agent's event stream.

        LangGraph's astream_events() emits events as the agent runs:
          - on_chat_model_stream: a text token from the LLM
          - on_tool_end: a tool finished executing, has its result
          - All other events are internal graph bookkeeping — we skip them.
        """
        try:
            async for event in agent.astream_events(
                {"messages": lc_messages},
                version="v2",
            ):
                kind = event.get("event")

                # Stream text tokens as they are generated
                if kind == "on_chat_model_stream":
                    chunk = event.get("data", {}).get("chunk")
                    if chunk and hasattr(chunk, "content") and chunk.content:
                        payload = json.dumps({"type": "token", "content": chunk.content})
                        yield f"data: {payload}\n\n"

                # Report tool calls so the UI can highlight executed actions
                elif kind == "on_tool_end":
                    tool_name = event.get("name", "")
                    tool_output = event.get("data", {}).get("output", "")
                    payload = json.dumps({
                        "type": "tool_call",
                        "name": tool_name,
                        "result": str(tool_output),
                    })
                    yield f"data: {payload}\n\n"

            # Signal stream completion
            yield f"data: {json.dumps({'type': 'done'})}\n\n"

        except Exception as e:
            error_payload = json.dumps({"type": "error", "content": str(e)})
            yield f"data: {error_payload}\n\n"
            yield f"data: {json.dumps({'type': 'done'})}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # Disable nginx buffering for SSE
        },
    )
