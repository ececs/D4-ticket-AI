"""
LangGraph tool factory for the AI agent.

The LLM cannot provide internal objects like database sessions or the current user.
Instead, `make_tools(db, actor)` returns a list of tools that already have those
objects captured in their closures — the LLM only sees and provides user-facing
arguments (title, status, ticket_id, etc.).

Each tool returns a plain string result that the LLM reads as tool output.

Available tools:
  query_tickets   — list tickets with optional filters
  get_ticket      — fetch a single ticket's details
  create_ticket   — create a new ticket
  change_status   — update a ticket's status
  add_comment     — post a comment on a ticket
  reassign_ticket — change a ticket's assignee
"""

import uuid

from langchain_core.tools import tool
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ticket import Ticket, TicketStatus, TicketPriority
from app.models.user import User
from app.models.comment import Comment
from app.services import ticket_service, notification_service


def make_tools(db: AsyncSession, actor: User) -> list:
    """
    Return a list of LangChain tools with `db` and `actor` bound via closure.

    This factory is called once per chat request with the request's DB session
    and authenticated user, so tools automatically act as that user without
    the LLM ever needing to supply auth information.
    """

    @tool
    async def query_tickets(
        status: str | None = None,
        priority: str | None = None,
        search: str | None = None,
        limit: int = 10,
    ) -> str:
        """
        List tickets with optional filters.

        Args:
            status: Filter by status — open, in_progress, in_review, or closed.
            priority: Filter by priority — low, medium, high, or critical.
            search: Search substring in ticket title.
            limit: Maximum number of results (default 10).
        """
        try:
            stmt = select(Ticket)
            if status:
                try:
                    stmt = stmt.where(Ticket.status == TicketStatus(status))
                except ValueError:
                    return f"Invalid status '{status}'. Valid: open, in_progress, in_review, closed."
            if priority:
                try:
                    stmt = stmt.where(Ticket.priority == TicketPriority(priority))
                except ValueError:
                    return f"Invalid priority '{priority}'. Valid: low, medium, high, critical."
            if search:
                stmt = stmt.where(Ticket.title.ilike(f"%{search}%"))

            stmt = stmt.limit(min(limit, 50)).order_by(Ticket.created_at.desc())
            result = await db.execute(stmt)
            tickets = result.scalars().all()

            if not tickets:
                return "No tickets found matching those filters."

            lines = [f"Found {len(tickets)} ticket(s):"]
            for t in tickets:
                lines.append(f"  [{t.status.value}] [{t.priority.value}] {t.title} (ID: {t.id})")
            return "\n".join(lines)
        except Exception as e:
            return f"Error querying tickets: {e}"

    @tool
    async def get_ticket(ticket_id: str) -> str:
        """
        Get full details of a single ticket.

        Args:
            ticket_id: UUID of the ticket.
        """
        try:
            tid = uuid.UUID(ticket_id)
        except ValueError:
            return f"Invalid ticket ID: '{ticket_id}'. Must be a UUID."
        try:
            ticket = await ticket_service.get_ticket(db, tid)
            if not ticket:
                return f"Ticket {ticket_id} not found."
            assignee = ticket.assignee.name if ticket.assignee else "Unassigned"
            author = ticket.author.name if ticket.author else "Unknown"
            return (
                f"Title: {ticket.title}\n"
                f"ID: {ticket.id}\n"
                f"Status: {ticket.status.value} | Priority: {ticket.priority.value}\n"
                f"Author: {author} | Assignee: {assignee}\n"
                f"Description: {ticket.description or 'None'}\n"
                f"Created: {ticket.created_at.isoformat()}"
            )
        except Exception as e:
            return f"Error fetching ticket: {e}"

    @tool
    async def create_ticket(
        title: str,
        description: str | None = None,
        priority: str = "medium",
        assignee_email: str | None = None,
    ) -> str:
        """
        Create a new ticket on behalf of the current user.

        Args:
            title: Short, descriptive title.
            description: Optional detailed description.
            priority: low, medium, high, or critical (default: medium).
            assignee_email: Email of the user to assign (optional).
        """
        try:
            try:
                prio = TicketPriority(priority)
            except ValueError:
                return f"Invalid priority '{priority}'. Valid: low, medium, high, critical."

            assignee_id = None
            if assignee_email:
                res = await db.execute(select(User).where(User.email == assignee_email))
                assignee = res.scalar_one_or_none()
                if not assignee:
                    return f"No user found with email '{assignee_email}'."
                assignee_id = assignee.id

            ticket = Ticket(
                title=title,
                description=description,
                priority=prio,
                status=TicketStatus.open,
                author_id=actor.id,
                assignee_id=assignee_id,
            )
            db.add(ticket)
            await db.commit()
            await db.refresh(ticket)

            if assignee_id and assignee_id != actor.id:
                # Notify assignee — load the assignee object first
                res = await db.execute(select(User).where(User.id == assignee_id))
                new_assignee = res.scalar_one_or_none()
                if new_assignee:
                    await notification_service.notify_ticket_assigned(
                        db, ticket=ticket, assignee=new_assignee, actor=actor
                    )

            return f"Ticket created. ID: {ticket.id} | Title: '{ticket.title}'"
        except Exception as e:
            return f"Error creating ticket: {e}"

    @tool
    async def change_status(ticket_id: str, new_status: str) -> str:
        """
        Change the status of a ticket.

        Args:
            ticket_id: UUID of the ticket.
            new_status: open, in_progress, in_review, or closed.
        """
        try:
            tid = uuid.UUID(ticket_id)
        except ValueError:
            return f"Invalid ticket ID: '{ticket_id}'."
        try:
            status = TicketStatus(new_status)
        except ValueError:
            return f"Invalid status '{new_status}'. Valid: open, in_progress, in_review, closed."
        try:
            ticket = await ticket_service.change_status(db, tid, status, actor)
            if not ticket:
                return f"Ticket {ticket_id} not found."
            return f"Status of '{ticket.title}' changed to '{new_status}'."
        except Exception as e:
            return f"Error changing status: {e}"

    @tool
    async def add_comment(ticket_id: str, content: str) -> str:
        """
        Add a comment to a ticket.

        Args:
            ticket_id: UUID of the ticket.
            content: Comment text to add.
        """
        try:
            tid = uuid.UUID(ticket_id)
        except ValueError:
            return f"Invalid ticket ID: '{ticket_id}'."
        try:
            res = await db.execute(select(Ticket).where(Ticket.id == tid))
            ticket = res.scalar_one_or_none()
            if not ticket:
                return f"Ticket {ticket_id} not found."

            comment = Comment(ticket_id=tid, author_id=actor.id, content=content)
            db.add(comment)
            await db.flush()

            await notification_service.notify_comment_added(db, ticket=ticket, comment=comment, actor=actor)
            await db.commit()

            return f"Comment added to '{ticket.title}'."
        except Exception as e:
            return f"Error adding comment: {e}"

    @tool
    async def reassign_ticket(ticket_id: str, assignee_email: str | None = None) -> str:
        """
        Reassign a ticket to a different user, or unassign it.

        Args:
            ticket_id: UUID of the ticket.
            assignee_email: Email of the new assignee. Pass null/None to unassign.
        """
        try:
            tid = uuid.UUID(ticket_id)
        except ValueError:
            return f"Invalid ticket ID: '{ticket_id}'."
        try:
            assignee_id = None
            if assignee_email:
                res = await db.execute(select(User).where(User.email == assignee_email))
                assignee = res.scalar_one_or_none()
                if not assignee:
                    return f"No user found with email '{assignee_email}'."
                assignee_id = assignee.id

            ticket = await ticket_service.reassign(db, tid, assignee_id, actor)
            if not ticket:
                return f"Ticket {ticket_id} not found."

            if assignee_email:
                return f"'{ticket.title}' reassigned to {assignee_email}."
            return f"'{ticket.title}' unassigned."
        except Exception as e:
            return f"Error reassigning ticket: {e}"

    return [query_tickets, get_ticket, create_ticket, change_status, add_comment, reassign_ticket]
