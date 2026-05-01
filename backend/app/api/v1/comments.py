"""
Comment routes.

Comments are attached to tickets and displayed chronologically in the ticket
detail view. Creating a comment automatically triggers a notification to the
ticket's author and assignee (if they are not the commenter).

NOTE: Full implementation is in Día 2.
"""

from fastapi import APIRouter

router = APIRouter(prefix="/tickets", tags=["Comments"])

# Full CRUD implementation added in Día 2
