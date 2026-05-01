"""
Ticket routes — CRUD + filtering + pagination.

This is the core resource of the API. All endpoints require authentication.

Filtering strategy:
  - All filters are optional query parameters.
  - Multiple filters are combined with AND logic.
  - Implemented via SQLAlchemy .where() chaining (not raw SQL) for safety.

Pagination:
  - Offset-based pagination with `page` and `size` parameters.
  - Returns total count for the frontend to render pagination controls.

NOTE: Full implementation is in Día 2. This file currently contains
the router stub so main.py can import it without errors.
"""

from fastapi import APIRouter

router = APIRouter(prefix="/tickets", tags=["Tickets"])

# Full CRUD implementation added in Día 2
