"""
LangGraph Tool Factory Module with Pydantic Validation.

This module defines the suite of tools available to the AI agent. It uses
Pydantic schemas for argument validation, ensuring that the LLM provides
correctly formatted data (UUIDs, Enums, etc.) before hitting the database.

Available Tools:
- query_tickets: search and filter tickets with pagination.
- get_ticket: fetch complete details of a single ticket.
- create_ticket: create a new support ticket.
- change_status: transition a ticket between workflow states.
- add_comment: append a message to a ticket thread.
- update_ticket: update any field in a ticket (priority, title, etc.).
- search_knowledge: query the semantic knowledge base (RAG).
- delete_ticket: permanently remove a ticket (requires interrupt).
"""

import uuid
import logging
import asyncio
from typing import Optional, List, Type
from pydantic import BaseModel, Field

from langchain_core.tools import tool
from sqlalchemy import select, case
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ticket import Ticket, TicketStatus, TicketPriority
from app.models.user import User
from app.models.comment import Comment
from app.services import ticket_service, notification_service, knowledge_service, comment_service, scraping_service

logger = logging.getLogger(__name__)

# --- Pydantic Schemas for Tool Arguments ---

class QueryTicketsSchema(BaseModel):
    status: Optional[str] = Field(None, description="Filter by: open, in_progress, in_review, closed")
    priority: Optional[str] = Field(None, description="Filter by: low, medium, high, critical")
    search: Optional[str] = Field(None, description="Text to search in the ticket title")
    limit: int = Field(10, ge=1, le=50, description="Max results to return")

class GetTicketSchema(BaseModel):
    ticket_id: str = Field(..., description="The UUID string of the ticket")

class CreateTicketSchema(BaseModel):
    title: str = Field(..., description="Concise title of the issue")
    description: Optional[str] = Field(None, description="Detailed context")
    priority: str = Field("medium", description="low, medium, high, or critical")
    assignee_email: Optional[str] = Field(None, description="Email of the user to assign")
    client_url: Optional[str] = Field(None, description="Client's website URL for analysis")
    client_summary: Optional[str] = Field(None, description="Brief summary of who the client is and what they do")

class ReassignTicketSchema(BaseModel):
    ticket_id: str = Field(..., description="UUID of the ticket")
    assignee_email: str = Field(..., description="Email of the user to assign, or 'unassign' to clear")

class ChangeStatusSchema(BaseModel):
    ticket_id: str = Field(..., description="UUID of the ticket")
    new_status: str = Field(..., description="New state: open, in_progress, in_review, closed")

class AddCommentSchema(BaseModel):
    ticket_id: str = Field(..., description="UUID of the target ticket")
    content: str = Field(..., description="Text content of the comment")

class UpdateTicketSchema(BaseModel):
    ticket_id: str = Field(..., description="UUID of the ticket")
    title: Optional[str] = Field(None, description="New title")
    description: Optional[str] = Field(None, description="New description")
    priority: Optional[str] = Field(None, description="New priority: low, medium, high, critical")
    assignee_email: Optional[str] = Field(None, description="New assignee email, or 'unassign'")
    client_url: Optional[str] = Field(None, description="New client website URL")
    client_summary: Optional[str] = Field(None, description="New client profile summary")

class SearchKnowledgeSchema(BaseModel):
    query: str = Field(..., description="The question or search phrase")
    k: int = Field(5, ge=1, le=10, description="Number of passages to retrieve")

class AIDiagnoseSchema(BaseModel):
    ticket_id: str = Field(..., description="UUID of the ticket to diagnose")

class DeleteTicketSchema(BaseModel):
    ticket_id: str = Field(..., description="UUID of the ticket to delete")

# --- Tool Factory ---

def make_tools(db: AsyncSession, actor: User) -> List:
    """
    Returns a collection of validated tools for the AI agent.
    """
    lock = asyncio.Lock()

    @tool(args_schema=QueryTicketsSchema)
    async def query_tickets(status=None, priority=None, search=None, limit=10) -> str:
        """List tickets with optional filters. Results include status, priority, and title."""
        logger.info(f"AI Tool: query_tickets(status={status}, priority={priority}, search={search})")
        async with lock:
            try:
                stmt = select(Ticket)
                if status:
                    try:
                        stmt = stmt.where(Ticket.status == TicketStatus(status))
                    except ValueError:
                        return f"Invalid status '{status}'."
                if priority:
                    try:
                        stmt = stmt.where(Ticket.priority == TicketPriority(priority))
                    except ValueError:
                        return f"Invalid priority '{priority}'."
                if search:
                    stmt = stmt.where(Ticket.title.ilike(f"%{search}%"))

                # Sort by priority (Critical > High > Medium > Low) then by oldest first (FIFO)
                priority_order = case(
                    (Ticket.priority == TicketPriority.critical, 1),
                    (Ticket.priority == TicketPriority.high, 2),
                    (Ticket.priority == TicketPriority.medium, 3),
                    (Ticket.priority == TicketPriority.low, 4),
                    else_=5
                )
                stmt = stmt.limit(limit).order_by(priority_order, Ticket.created_at.asc())
                
                logger.info(f"Executing query_tickets with limit {limit}")
                result = await db.execute(stmt)
                tickets = result.scalars().all()
                logger.info(f"Query finished, found {len(tickets)} tickets")

                if not tickets:
                    return "No tickets found with the specified filters."

                return "\n".join([f"  [{t.status.value}] [{t.priority.value}] {t.title} (ID: {t.id})" for t in tickets])
            except Exception as e:
                return f"Error: {e}"

    @tool(args_schema=GetTicketSchema)
    async def get_ticket(ticket_id: str) -> str:
        """Get full details of a single ticket."""
        async with lock:
            try:
                tid = uuid.UUID(ticket_id)
                ticket = await ticket_service.get_ticket(db, tid)
                if not ticket:
                    return "Ticket not found."
                return f"Title: {ticket.title}\nStatus: {ticket.status.value}\nDescription: {ticket.description}"
            except Exception as e:
                return f"Error: {e}"

    @tool(args_schema=CreateTicketSchema)
    async def create_ticket(title, description=None, priority="medium", assignee_email=None, client_url=None, client_summary=None) -> str:
        """Create a new support ticket with optional client context (URL/Summary)."""
        async with lock:
            try:
                prio = TicketPriority(priority)
                assignee_id = None
                if assignee_email:
                    res = await db.execute(select(User).where(User.email == assignee_email))
                    user = res.scalar_one_or_none()
                    if not user: return f"User {assignee_email} not found."
                    assignee_id = user.id

                ticket = await ticket_service.create_ticket(
                    db, 
                    title=title, 
                    description=description, 
                    priority=prio, 
                    author_id=actor.id, 
                    assignee_id=assignee_id,
                    client_url=client_url,
                    client_summary=client_summary
                )
                return f"Ticket created. ID: {ticket.id}"
            except Exception as e:
                return f"Error: {e}"

    @tool(args_schema=ChangeStatusSchema)
    async def change_status(ticket_id: str, new_status: str) -> str:
        """Update a ticket's status."""
        async with lock:
            try:
                tid = uuid.UUID(ticket_id)
                status = TicketStatus(new_status)
                ticket = await ticket_service.update_ticket(db, tid, {"status": status}, actor)
                if not ticket: return "Ticket not found."
                return f"Status updated to {new_status}."
            except Exception as e:
                return f"Error: {e}"

    @tool(args_schema=AddCommentSchema)
    async def add_comment(ticket_id: str, content: str) -> str:
        """Add a comment to a ticket thread."""
        async with lock:
            try:
                tid = uuid.UUID(ticket_id)
                comment = await comment_service.create_comment(db, ticket_id=tid, content=content, author=actor)
                if not comment:
                    return f"Ticket {ticket_id} not found."

                return "Comment successfully added."
            except Exception as e:
                return f"Error: {e}"

    @tool(args_schema=UpdateTicketSchema)
    async def update_ticket(
        ticket_id: str, 
        title=None, 
        description=None, 
        priority=None, 
        assignee_email=None, 
        client_url=None, 
        client_summary=None
    ) -> str:
        """Update any ticket field. Use 'assignee_email' to reassign, or set it to 'unassign' to clear it."""
        async with lock:
            try:
                tid = uuid.UUID(ticket_id)
                update_data = {}
                if title: update_data["title"] = title
                if description: update_data["description"] = description
                if priority: update_data["priority"] = TicketPriority(priority)
                if client_url: update_data["client_url"] = client_url
                if client_summary: update_data["client_summary"] = client_summary
                
                if assignee_email:
                    if assignee_email.lower() == "unassign":
                        update_data["assignee_id"] = None
                    else:
                        res = await db.execute(select(User).where(User.email == assignee_email))
                        user = res.scalar_one_or_none()
                        if not user: return f"User {assignee_email} not found."
                        update_data["assignee_id"] = user.id

                updated_ticket = await ticket_service.update_ticket(db, tid, update_data, actor)
                
                # If URL changed, trigger background scraping
                if client_url:
                    import asyncio
                    asyncio.create_task(scraping_service.scrape_and_index_url(db, tid, client_url))

                return "Ticket successfully updated."
            except Exception as e:
                return f"Error: {e}"

    @tool(args_schema=SearchKnowledgeSchema)
    async def search_knowledge(query: str, k: int = 5) -> str:
        """Query the knowledge base."""
        async with lock:
            try:
                chunks = await knowledge_service.search(db, query, k=k)
                return "\n\n".join(chunks) if chunks else "No information found."
            except Exception as e:
                return f"Error: {e}"

    @tool(args_schema=AIDiagnoseSchema)
    async def ai_diagnose_ticket(ticket_id: str) -> str:
        """
        AI Co-pilot: Generate a detailed diagnosis and suggested solution for a ticket.
        """
        async with lock:
            try:
                from app.services import ai_copilot_service
                tid = uuid.UUID(ticket_id)
                diagnosis = await ai_copilot_service.get_ticket_diagnosis(db, tid)
                return diagnosis
            except Exception as e:
                return f"Error al generar diagnóstico: {e}"

    @tool(args_schema=ReassignTicketSchema)
    async def reassign_ticket(ticket_id: str, assignee_email: str) -> str:
        """
        Reassign a ticket to another user by their email.
        """
        async with lock:
            try:
                tid = uuid.UUID(ticket_id)
                assignee_id = None
                if assignee_email.lower() != "unassign":
                    res = await db.execute(select(User).where(User.email == assignee_email))
                    user = res.scalar_one_or_none()
                    if not user: return f"User {assignee_email} not found."
                    assignee_id = user.id

                await ticket_service.update_ticket(db, tid, {"assignee_id": assignee_id}, actor)
                return f"Ticket successfully reassigned to {assignee_email}."
            except Exception as e:
                return f"Error reassigning ticket: {e}"

    @tool(args_schema=DeleteTicketSchema)
    async def delete_ticket(ticket_id: str) -> str:
        """
        Request permanent deletion of a ticket. Always pauses for human approval
        before anything is deleted — the UI shows a confirmation dialog.
        """
        async with lock:
            try:
                tid = uuid.UUID(ticket_id)
                result = await db.execute(select(Ticket).where(Ticket.id == tid))
                ticket = result.scalar_one_or_none()
                if not ticket:
                    return "Ticket not found."
                title = ticket.title
            except ValueError:
                return f"Invalid ticket ID: {ticket_id}"
            except Exception as e:
                return f"Error: {e}"

        # Return the marker with the real title — the router intercepts this
        # and sends a 'confirmation_required' SSE event to the frontend.
        return f"__DELETE_REQUESTED__:{ticket_id}:{title}"

    return [
        query_tickets, 
        get_ticket, 
        create_ticket, 
        change_status, 
        add_comment, 
        update_ticket, 
        reassign_ticket,
        search_knowledge,
        ai_diagnose_ticket,
        delete_ticket
    ]
