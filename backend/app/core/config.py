"""
Application configuration.

Uses pydantic-settings to load configuration from environment variables (or a .env file).
All settings are typed and validated at startup — if a required value is missing or
has the wrong type, the application will fail fast with a clear error message.

Environment variables take precedence over .env file values.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Central settings object loaded from environment variables.

    All fields have sensible defaults for local development with Docker Compose.
    In production (Railway/Vercel), override via the hosting platform's env vars.
    """

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # --- Database ---
    # asyncpg driver for async I/O — never use the sync postgres:// URL here
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@db:5432/ticketai"

    # --- Authentication ---
    # SECRET_KEY: used to sign/verify JWT tokens. Must be ≥32 random chars in production.
    SECRET_KEY: str = "change-me-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 10080  # 7 days — long session for developer UX

    # Google OAuth 2.0 credentials (from Google Cloud Console)
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    FRONTEND_URL: str = "http://localhost:3000"
    BACKEND_URL: str = "http://localhost:8000"
    
    # List of emails allowed to log in. Use ["*"] to allow anyone.
    # Supports domains: use "@domain.com" to allow everyone from that org.
    # In production, set this to your email and "@orbidi.com".
    ALLOWED_EMAILS: list[str] = ["*"]

    # --- File Storage (S3-compatible via boto3) ---
    # Local dev: MinIO container. Production: Cloudflare R2 (same boto3 code, different endpoint)
    STORAGE_ENDPOINT: str = "http://minio:9000"
    STORAGE_ACCESS_KEY: str = "minioadmin"
    STORAGE_SECRET_KEY: str = "minioadmin"
    STORAGE_BUCKET: str = "attachments"
    STORAGE_REGION: str = "us-east-1"

    # --- AI Agent ---
    # Gemini 1.5 Flash by default (free tier).
    # Switch to "openai" + gpt-4o-mini for guaranteed reliability and performance.
    AI_PROVIDER: str = "google"  # "google" | "anthropic" | "openai"
    AI_MODEL: str = "gemini-2.5-flash"
    GOOGLE_API_KEY: str = ""
    ANTHROPIC_API_KEY: str = ""
    OPENAI_API_KEY: str = ""

    # --- Observability (LangSmith) ---
    # Set LANGSMITH_TRACING=true + LANGSMITH_API_KEY in Railway to enable agent tracing.
    # Traces every LLM call, tool invocation, latency, and token usage — zero code changes needed.
    LANGSMITH_TRACING: bool = False
    LANGSMITH_API_KEY: str = ""
    LANGSMITH_PROJECT: str = "d4-ticket-ai"
    LANGSMITH_ENDPOINT: str = "https://api.smith.langchain.com"

    # --- Redis Cache ---
    # Optional: set REDIS_URL to enable caching on the ticket list endpoint.
    # If empty, the endpoint runs without cache (graceful degradation).
    REDIS_URL: str = ""

    # --- Business Rules ---
    MAX_ATTACHMENT_SIZE_MB: int = 10
    ALLOWED_MIME_TYPES: list[str] = [
        "image/jpeg", "image/png", "image/gif", "image/webp",
        "application/pdf",
        "application/msword",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "text/plain",
    ]


# Singleton instance — import this in all modules that need settings
settings = Settings()
