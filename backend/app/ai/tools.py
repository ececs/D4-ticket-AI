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
- reassign_ticket: change the assigned user for a ticket.
- search_knowledge: query the semantic knowledge base (RAG).

Architecture:
- Args Schemas: Pydantic models that define the input contract for each tool.
- Tool Factory: Closure-based injection of DB sessions and authenticated users.
- Type Safety: Uses TicketStatus and TicketPriority Enums for strict validation.
"""

import uuid
import logging
from typing import Optional, List, Type
from pydantic import BaseModel, Field

from langchain_core.tools import tool
from sqlalchemy import select, case
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ticket import Ticket, TicketStatus, TicketPriority
from app.models.user import User
from app.models.comment import Comment
from app.services import ticket_service, notification_service, knowledge_service, comment_service

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

class ChangeStatusSchema(BaseModel):
    ticket_id: str = Field(..., description="UUID of the ticket")
    new_status: str = Field(..., description="New state: open, in_progress, in_review, closed")

class AddCommentSchema(BaseModel):
    ticket_id: str = Field(..., description="UUID of the target ticket")
    content: str = Field(..., description="Text content of the comment")

class ReassignTicketSchema(BaseModel):
    ticket_id: str = Field(..., description="UUID of the ticket")
    assignee_email: Optional[str] = Field(None, description="New assignee email, or None to unassign")

class SearchKnowledgeSchema(BaseModel):
    query: str = Field(..., description="The question or search phrase")
    k: int = Field(5, ge=1, le=10, description="Number of passages to retrieve")

# --- Tool Factory ---

def make_tools(db: AsyncSession, actor: User) -> List:
    """
    Returns a collection of validated tools for the AI agent.
    """

    @tool(args_schema=QueryTicketsSchema)
    async def query_tickets(status=None, priority=None, search=None, limit=10) -> str:
        """List tickets with optional filters. Results include status, priority, and title."""
        logger.info(f"AI Tool: query_tickets(status={status}, priority={priority}, search={search})")
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
        try:
            tid = uuid.UUID(ticket_id)
            ticket = await ticket_service.get_ticket(db, tid)
            if not ticket:
                return "Ticket not found."
            return f"Title: {ticket.title}\nStatus: {ticket.status.value}\nDescription: {ticket.description}"
        except Exception as e:
            return f"Error: {e}"

    @tool(args_schema=CreateTicketSchema)
    async def create_ticket(title, description=None, priority="medium", assignee_email=None) -> str:
        """Create a new support ticket."""
        try:
            prio = TicketPriority(priority)
            assignee_id = None
            if assignee_email:
                res = await db.execute(select(User).where(User.email == assignee_email))
                user = res.scalar_one_or_none()
                if not user: return f"User {assignee_email} not found."
                assignee_id = user.id

            ticket = Ticket(title=title, description=description, priority=prio, author_id=actor.id, assignee_id=assignee_id)
            db.add(ticket)
            await db.commit()
            return f"Ticket created. ID: {ticket.id}"
        except Exception as e:
            return f"Error: {e}"

    @tool(args_schema=ChangeStatusSchema)
    async def change_status(ticket_id: str, new_status: str) -> str:
        """Update a ticket's status."""
        try:
            tid = uuid.UUID(ticket_id)
            status = TicketStatus(new_status)
            ticket = await ticket_service.change_status(db, tid, status, actor)
            if not ticket: return "Ticket not found."
            return f"Status updated to {new_status}."
        except Exception as e:
            return f"Error: {e}"

    @tool(args_schema=AddCommentSchema)
    async def add_comment(ticket_id: str, content: str) -> str:
        """Add a comment to a ticket thread."""
        try:
            tid = uuid.UUID(ticket_id)
            comment = await comment_service.create_comment(db, ticket_id=tid, content=content, author=actor)
            if not comment:
                return f"Ticket {ticket_id} not found."

            return "Comment successfully added."
        except Exception as e:
            return f"Error: {e}"

    @tool(args_schema=ReassignTicketSchema)
    async def reassign_ticket(ticket_id: str, assignee_email=None) -> str:
        """Change the ticket assignee."""
        try:
            tid = uuid.UUID(ticket_id)
            assignee_id = None
            if assignee_email:
                res = await db.execute(select(User).where(User.email == assignee_email))
                user = res.scalar_one_or_none()
                if not user: return "User not found."
                assignee_id = user.id
            
            await ticket_service.reassign(db, tid, assignee_id, actor)
            return "Ticket reassigned."
        except Exception as e:
            return f"Error: {e}"

    @tool(args_schema=SearchKnowledgeSchema)
    async def search_knowledge(query: str, k: int = 5) -> str:
        """Query the knowledge base."""
        try:
            chunks = await knowledge_service.search(db, query, k=k)
            return "\n\n".join(chunks) if chunks else "No information found."
        except Exception as e:
            return f"Error: {e}"

    return [query_tickets, get_ticket, create_ticket, change_status, add_comment, reassign_ticket, search_knowledge]
