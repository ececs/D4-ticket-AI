from pydantic import BaseModel, HttpUrl

class IngestRequest(BaseModel):
    url: HttpUrl

class IngestResponse(BaseModel):
    url: str
    chunks_created: int
