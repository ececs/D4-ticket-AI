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
from app.ai.checkpoint import get_checkpointer
from app.ai.state import AgentState


SYSTEM_PROMPT = """You are an AI assistant for D4-Ticket AI, a professional ticketing system.
You help users manage their tickets through natural language.

You have access to the following tools:
- query_tickets: search and filter tickets (returns status, priority, title, and ID)
- get_ticket: get details of a specific ticket
- create_ticket: create a new ticket
- change_status: change a ticket's status
- add_comment: add a comment to a ticket
- reassign_ticket: reassign a ticket to another user
- search_knowledge: search the internal knowledge base for documentation, guides, or context

Guidelines:
- Always respond in the same language the user is writing in (Spanish or English).
- When you perform an action (create, update, comment), confirm it clearly.
- If you need a ticket ID and the user gave a partial ID or title, use query_tickets first.
- To find "urgent" tickets, use query_tickets (the most urgent will be at the top). The information in the list is sufficient; DO NOT call get_ticket for every result unless the user asks for full details.
- If multiple tickets have the same maximum priority, the oldest ones are considered more urgent. Explain this reasoning to the user (e.g., "This ticket is critical and has been open the longest").
- Be concise and friendly. Avoid unnecessary technical jargon.
- Never invent ticket IDs or user emails — always verify with tools first.
- If an action fails, explain why clearly.
- If a question seems to be about a process, policy, or documentation topic, search_knowledge before answering from your own knowledge.
"""


def get_llm() -> BaseChatModel:
    """
    Construct the LLM with automatic fallback.
    Primary: Gemini 2.0 Flash (Fast & Modern)
    Fallback: OpenAI GPT-4o-mini (Reliable & Cheap)
    """
    # 1. Initialize Gemini (Primary)
    from langchain_google_genai import ChatGoogleGenerativeAI
    gemini = ChatGoogleGenerativeAI(
        model="gemini-2.0-flash", 
        google_api_key=settings.GOOGLE_API_KEY,  # type: ignore[arg-type]
        temperature=0,
        streaming=True,
        max_retries=0, # FAIL FAST: jump to OpenAI immediately if quota is hit
    )

    # 2. Initialize OpenAI (Fallback)
    # Only if the key is provided in settings
    if settings.OPENAI_API_KEY:
        from langchain_openai import ChatOpenAI
        openai = ChatOpenAI(
            model="gpt-4o-mini",
            api_key=settings.OPENAI_API_KEY,  # type: ignore[arg-type]
            temperature=0,
            streaming=True,
            request_timeout=30.0, # Don't wait more than 30s
        )
        # Apply automatic fallback logic: if Gemini fails, use OpenAI
        return gemini.with_fallbacks([openai])
    
    return gemini


def build_agent(db: AsyncSession, actor: User):
    """
    Build a ReAct agent for a single request.
    """
    llm = get_llm()
    tools = make_tools(db, actor)
    
    # Restoring persistent PostgreSQL memory
    checkpointer = get_checkpointer()

    return create_react_agent(
        model=llm,
        tools=tools,
        prompt=SystemMessage(content=SYSTEM_PROMPT),
        checkpointer=checkpointer,
        state_schema=AgentState,
    )
