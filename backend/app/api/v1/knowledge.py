from fastapi import APIRouter, HTTPException, status
from app.core.dependencies import CurrentUser, DB
from app.schemas.knowledge import IngestRequest, IngestResponse
from app.services import knowledge_service

router = APIRouter(prefix="/knowledge", tags=["Knowledge"])


@router.post(
    "",
    response_model=IngestResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Ingest a URL into the AI knowledge base",
)
async def ingest_url(body: IngestRequest, db: DB, current_user: CurrentUser):
    """
    Scrape and embed content from a URL to expand the assistant's knowledge.
    """
    try:
        # The service now returns an IngestResponse object directly
        return await knowledge_service.ingest_url(db, str(body.url))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
