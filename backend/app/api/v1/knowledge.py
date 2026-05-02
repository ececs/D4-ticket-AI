from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, HttpUrl

from app.core.dependencies import CurrentUser, DB
from app.services import knowledge_service

router = APIRouter(prefix="/knowledge", tags=["Knowledge"])


class IngestRequest(BaseModel):
    url: HttpUrl


class IngestResponse(BaseModel):
    url: str
    chunks_created: int


@router.post(
    "",
    response_model=IngestResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Ingest a URL into the AI knowledge base",
)
async def ingest_url(body: IngestRequest, db: DB, current_user: CurrentUser):
    try:
        result = await knowledge_service.ingest_url(db, str(body.url))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return IngestResponse(**result)
