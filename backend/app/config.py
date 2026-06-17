from functools import lru_cache
from os import getenv

from dotenv import load_dotenv

load_dotenv()


class Settings:
    database_url: str = getenv("DATABASE_URL", "sqlite:///./geoatlas_local.db")
    supabase_url: str | None = getenv("SUPABASE_URL")
    supabase_anon_key: str | None = getenv("SUPABASE_ANON_KEY")
    supabase_service_role_key: str | None = getenv("SUPABASE_SERVICE_ROLE_KEY")
    public_base_url: str = getenv("GEOATLAS_PUBLIC_BASE_URL", "http://127.0.0.1:8000")
    admin_cors_origins: list[str] = [
        origin.strip()
        for origin in getenv(
            "GEOATLAS_ADMIN_CORS_ORIGINS",
            "http://127.0.0.1:8000,http://localhost:8000",
        ).split(",")
        if origin.strip()
    ]
    fetch_timeout_seconds: int = int(getenv("GEOATLAS_FETCH_TIMEOUT_SECONDS", "10"))
    max_feed_bytes: int = int(getenv("GEOATLAS_MAX_FEED_BYTES", "5242880"))
    user_agent: str = getenv("GEOATLAS_USER_AGENT", "GeoAtlasDataCollector/1.0")


@lru_cache
def get_settings() -> Settings:
    return Settings()
