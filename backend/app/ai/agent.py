"""
LangGraph AI agent definition.

Uses langgraph.prebuilt.create_react_agent — a pre-built ReAct agent that:
  1. Sends the conversation to the LLM.
  2. If the LLM calls a tool, executes it and loops back.
  3. When the LLM produces a final text response, the loop ends.

Provider abstraction:
  The LLM is constructed by get_llm() based on AI_PROVIDER / AI_MODEL env vars.

System prompt:
  Tells the agent it is a ticket management assistant, what tools it has, and to
  always reply in the same language the user wrote in (Spanish or English).
"""

import logging
from langchain_core.messages import SystemMessage
from langchain_core.language_models import BaseChatModel
from langgraph.prebuilt import create_react_agent
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.user import User
from app.ai.tools import make_tools
from app.ai.checkpoint import get_checkpointer
from app.ai.state import AgentState

logger = logging.getLogger(__name__)
_llm_singleton: BaseChatModel | None = None


SYSTEM_PROMPT = """You are an AI assistant for D4-Ticket AI, a professional ticketing system.
You help users manage their tickets through natural language.

You have access to the following tools:
- query_tickets: search and filter tickets (returns status, priority, title, and ID)
- get_ticket: get details of a specific ticket
- create_ticket: create a new ticket
- change_status: change a ticket's status
- add_comment: add a comment to a ticket
- update_ticket: update title, description or client info
- reassign_ticket: reassign a ticket to another user by their email
- delete_ticket: request deletion of a ticket. Call this tool immediately when the user asks to delete a ticket. The system will automatically show a confirmation dialog to the user — you do NOT need to ask for confirmation yourself.
- search_knowledge: search the internal knowledge base for documentation, guides, or context

Guidelines:
- PRINCIPLE OF HUMAN-IN-THE-LOOP:
  - DIRECT COMMANDS: If the user explicitly asks you to perform an action (e.g., "Create a ticket for X", "Change ticket 123 to closed"), execute the tool immediately.
  - SUGGESTIONS/DIAGNOSIS: If YOU identify a problem or suggest a solution (e.g., "I think this ticket should be reassigned to Network experts"), YOU MUST NOT call the tool automatically. Instead, explain your reasoning and ASK THE USER for confirmation (e.g., "¿Quieres que lo reasigne por ti?").
  - Never modify the database state based on your own induction without explicit human consent.
- CONTEXT RESOLUTION & EXECUTION (WHICH TICKET TO MODIFY):
  - If the user issues a direct command (e.g., "change to high priority", "close this"), you MUST execute the appropriate tool IMMEDIATELY without asking for confirmation, using this priority:
    1. EXPLICIT: If the user explicitly names a specific ticket title or ID in their message, ALWAYS act on that.
    2. SELECTED/VIEWED: If no ticket is named, use the "CURRENTLY VIEWING" or "USER HAS SELECTED THESE TICKETS" from the system context. Execute the tool for EACH selected ticket IMMEDIATELY. The user's current selection ALWAYS overrides the conversation history.
    3. AMBIGUOUS: Only ask for clarification if there is no named ticket AND no selected/viewed ticket.
- TEMPORAL AWARENESS & GREETINGS:
  - ONLY if the user's message is EXCLUSIVELY a greeting (e.g., "hola", "buenas", "hi") AND there is a long period of inactivity, greet them back and mention any pending task.
  - IF THE USER GIVES A DIRECT COMMAND (e.g., "borra el ticket", "ponlo en alta"), EXECUTE IT IMMEDIATELY regardless of the time passed since the last interaction. Commands ALWAYS override greetings.
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
    Return the LLM singleton, building it on first call.
    Primary: Gemini 2.0 Flash — Fallback: OpenAI GPT-4o-mini.
    Cached at module level to avoid re-instantiating HTTP clients per request.
    """
    global _llm_singleton
    if _llm_singleton is not None:
        return _llm_singleton
    _llm_singleton = _build_llm()
    return _llm_singleton


def _build_llm() -> BaseChatModel:
    primary_model = settings.AI_MODEL or "gemini-2.0-flash"

    # 1. Primary LLM
    if settings.AI_PROVIDER == "google":
        if not settings.GOOGLE_API_KEY:
            raise ValueError("GOOGLE_API_KEY no encontrada. Revisa tu archivo .env en la carpeta backend.")
        from langchain_google_genai import ChatGoogleGenerativeAI
        primary_llm = ChatGoogleGenerativeAI(
            model=primary_model,
            google_api_key=settings.GOOGLE_API_KEY,
            temperature=0,
            streaming=True,
            max_retries=0,  # fail fast to trigger fallback
        )
    else:
        if not settings.OPENAI_API_KEY:
            raise ValueError("OPENAI_API_KEY no encontrada para el proveedor primario.")
        from langchain_openai import ChatOpenAI
        primary_llm = ChatOpenAI(
            model=primary_model,
            api_key=settings.OPENAI_API_KEY,
            temperature=0,
            streaming=True,
        )

    # 2. Fallback LLM — only for transient errors (network, quota), not config errors
    if settings.AI_PROVIDER == "google" and settings.OPENAI_API_KEY:
        try:
            from langchain_openai import ChatOpenAI
            import httpx
            fallback_llm = ChatOpenAI(
                model="gpt-4o-mini",
                api_key=settings.OPENAI_API_KEY,
                temperature=0,
                streaming=True,
                request_timeout=30.0,
            )
            logger.info("AI Agent: %s (with GPT-4o-mini fallback)", primary_model)
            # Envolvemos el LLM con fallbacks para que sea resiliente
            return primary_llm.with_fallbacks(
                [fallback_llm],
                exceptions_to_handle=(Exception,),
            )
        except ImportError:
            logger.warning("AI Agent: langchain-openai not installed — fallback disabled.")
    elif settings.AI_PROVIDER == "google":
        logger.warning("AI Agent: OPENAI_API_KEY not set — fallback disabled.")

    logger.info("AI Agent: %s (no fallback)", primary_model)
    return primary_llm


def build_agent(db: AsyncSession, actor: User, system_context: str = ""):
    """
    Build a ReAct agent for a single request.
    """
    llm = get_llm()
    tools = make_tools(db, actor)
    
    # Restoring persistent PostgreSQL memory
    checkpointer = get_checkpointer()

    full_prompt = SYSTEM_PROMPT
    if system_context:
        full_prompt += f"\n\n{system_context}"

    return create_react_agent(
        model=llm,
        tools=tools,
        prompt=SystemMessage(content=full_prompt),
        checkpointer=checkpointer,
        state_schema=AgentState,
    )
