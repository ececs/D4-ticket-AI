from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from app.ai.tools import make_tools
from app.models.ticket import Ticket, TicketPriority
from app.models.user import User


def _capture_task(coro):
    coro.close()
    return MagicMock()


async def test_update_ticket_tool_schedules_scrape_with_ticket_id_and_url(
    db_session,
    test_user: User,
):
    ticket = Ticket(
        title="Client site ticket",
        description="Used to validate AI update tool scraping hook.",
        priority=TicketPriority.medium,
        author_id=test_user.id,
    )
    db_session.add(ticket)
    await db_session.commit()

    tools = make_tools(db_session, test_user)
    update_tool = next(tool for tool in tools if tool.name == "update_ticket")

    with (
        patch("app.ai.tools.ticket_service.update_ticket", new=AsyncMock(return_value=SimpleNamespace(id=ticket.id))),
        patch("app.ai.tools.scraping_service.scrape_and_index_url", new=AsyncMock()) as mock_scrape,
        patch("app.ai.tools.asyncio.create_task", side_effect=_capture_task) as mock_create_task,
    ):
        result = await update_tool.ainvoke(
            {
                "ticket_id": str(ticket.id),
                "client_url": "https://example.com/status",
            }
        )

    assert result == "Ticket successfully updated."
    mock_scrape.assert_called_once_with(ticket.id, "https://example.com/status")
    mock_create_task.assert_called_once()


async def test_update_ticket_tool_does_not_schedule_scrape_without_client_url(
    db_session,
    test_user: User,
):
    ticket = Ticket(
        title="Plain ticket",
        description="Used to validate AI update tool without URL side effects.",
        priority=TicketPriority.medium,
        author_id=test_user.id,
    )
    db_session.add(ticket)
    await db_session.commit()

    tools = make_tools(db_session, test_user)
    update_tool = next(tool for tool in tools if tool.name == "update_ticket")

    with (
        patch("app.ai.tools.ticket_service.update_ticket", new=AsyncMock(return_value=SimpleNamespace(id=ticket.id))),
        patch("app.ai.tools.scraping_service.scrape_and_index_url", new=AsyncMock()) as mock_scrape,
        patch("app.ai.tools.asyncio.create_task", side_effect=_capture_task) as mock_create_task,
    ):
        result = await update_tool.ainvoke(
            {
                "ticket_id": str(ticket.id),
                "title": "Renamed without URL",
            }
        )

    assert result == "Ticket successfully updated."
    mock_scrape.assert_not_called()
    mock_create_task.assert_not_called()
