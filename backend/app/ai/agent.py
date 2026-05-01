"""
LangGraph AI agent definition.

Uses langgraph.prebuilt.create_react_agent — a pre-built ReAct agent that:
  1. Sends the conversation to the LLM.
  2. If the LLM calls a tool, executes it and loops back.
  3. When the LLM produces a final text response, the loop ends.

Provider abstraction:
  The LLM is constructed by get_llm() based on AI_PROVIDER / AI_MODEL env vars.
  Switching from Gemini to Claude requires only changing two env vars — no code change.

System prompt:
  Tells the agent it is a ticket management assistant, what tools it has, and to
  always reply in the same language the user wrote in (Spanish or English).
"""

from langchain_core.messages import SystemMessage
from langchain_core.language_models import BaseChatModel
from langgraph.prebuilt import create_react_agent
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.user import User
from app.ai.tools import make_tools


SYSTEM_PROMPT = """You are an AI assistant for D4-Ticket AI, a professional ticketing system.
You help users manage their tickets through natural language.

You have access to the following tools:
- query_tickets: search and filter tickets
- get_ticket: get details of a specific ticket
- create_ticket: create a new ticket
- change_status: change a ticket's status
- add_comment: add a comment to a ticket
- reassign_ticket: reassign a ticket to another user

Guidelines:
- Always respond in the same language the user is writing in (Spanish or English).
- When you perform an action (create, update, comment), confirm it clearly.
- If you need a ticket ID and the user gave a partial ID or title, use query_tickets first.
- Be concise and friendly. Avoid unnecessary technical jargon.
- Never invent ticket IDs or user emails — always verify with tools first.
- If an action fails, explain why clearly.
"""


def get_llm() -> BaseChatModel:
    """
    Construct the LLM based on the AI_PROVIDER environment variable.

    Supported providers:
      - "google": Gemini 2.5 Flash (free tier, 500 req/day) — default
      - "anthropic": Claude Haiku 4.5 (reliable fallback, low cost)

    Switching: set AI_PROVIDER and AI_MODEL in .env, restart the backend.
    """
    if settings.AI_PROVIDER == "anthropic":
        from langchain_anthropic import ChatAnthropic
        return ChatAnthropic(
            model=settings.AI_MODEL,
            api_key=settings.ANTHROPIC_API_KEY,  # type: ignore[arg-type]
            temperature=0,
        )
    else:
        # Default: Google Gemini
        from langchain_google_genai import ChatGoogleGenerativeAI
        return ChatGoogleGenerativeAI(
            model=settings.AI_MODEL,
            google_api_key=settings.GOOGLE_API_KEY,  # type: ignore[arg-type]
            temperature=0,
        )


def build_agent(db: AsyncSession, actor: User):
    """
    Build a ReAct agent for a single request.

    A fresh agent is created per request so the tools have the correct
    db session and actor for that request's context.

    Args:
        db: The SQLAlchemy async session for this request.
        actor: The authenticated user — tools act on their behalf.

    Returns:
        A compiled LangGraph CompiledGraph ready to stream.
    """
    llm = get_llm()
    tools = make_tools(db, actor)

    return create_react_agent(
        model=llm,
        tools=tools,
        state_modifier=SystemMessage(content=SYSTEM_PROMPT),
    )
