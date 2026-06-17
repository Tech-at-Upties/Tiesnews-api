from pathlib import Path

from fastapi import Depends, FastAPI, Header, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.admin_keys import validate_admin_key
from app.config import get_settings
from app.database import Base, engine, get_db
from app.feed_utils import FeedError
from app.models import EventCandidate, ExternalSource, IngestionJob, NormalizedItem
from app.schemas import (
    DetectRequest,
    DetectResponse,
    IngestResponse,
    JobResponse,
    PublicEvent,
    PublicItem,
    PublicItemsResponse,
    PublicSource,
    SourceCreate,
    SourceResponse,
    SourceUpdate,
)
from app.services import create_source, detect_source, run_ingestion

settings = get_settings()

app = FastAPI(
    title="GeoAtlas Data Collection API",
    description="Standalone RSS/Atom source collection and public output API for GeoAtlas.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.admin_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.on_event("startup")
def initialize_database() -> None:
    try:
        Base.metadata.create_all(bind=engine)
        app.state.database_ready = True
        app.state.database_error = None
    except SQLAlchemyError as exc:
        app.state.database_ready = False
        app.state.database_error = str(exc)


def require_admin(x_admin_key: str | None = Header(default=None), db: Session = Depends(get_db)) -> None:
    try:
        is_valid = validate_admin_key(db, x_admin_key)
    except SQLAlchemyError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Admin key validation database unavailable.") from exc
    if not is_valid:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or missing admin API key.")


def source_or_404(db: Session, source_id: str) -> ExternalSource:
    source = db.get(ExternalSource, source_id)
    if not source or source.archived:
        raise HTTPException(status_code=404, detail="Source not found.")
    return source


@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/health")
def health(db: Session = Depends(get_db)) -> dict:
    database_status = "ok"
    database_error = None
    try:
        db.execute(select(1))
    except SQLAlchemyError as exc:
        database_status = "error"
        database_error = str(exc).splitlines()[0]
    return {
        "status": "ok" if database_status == "ok" else "degraded",
        "database": database_status,
        "database_error": database_error,
        "service": "geoatlas-data-collection",
        "supabase": {
            "url_configured": bool(settings.supabase_url),
            "anon_key_configured": bool(settings.supabase_anon_key),
            "service_role_key_configured": bool(settings.supabase_service_role_key),
            "postgres_connection_configured": not settings.database_url.startswith("sqlite"),
        },
    }


@app.post("/api/v1/sources/detect", response_model=DetectResponse, dependencies=[Depends(require_admin)])
def detect_feed(payload: DetectRequest) -> dict:
    try:
        return detect_source(str(payload.url), payload.fetch_sample_items)
    except FeedError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/v1/sources/rss", response_model=SourceResponse, dependencies=[Depends(require_admin)])
def add_rss_source(payload: SourceCreate, db: Session = Depends(get_db)) -> ExternalSource:
    try:
        return create_source(db, payload)
    except FeedError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/v1/sources", response_model=list[SourceResponse], dependencies=[Depends(require_admin)])
def list_sources(
    db: Session = Depends(get_db),
    include_archived: bool = False,
    limit: int = Query(default=50, ge=1, le=200),
) -> list[ExternalSource]:
    statement = select(ExternalSource).order_by(desc(ExternalSource.created_at)).limit(limit)
    if not include_archived:
        statement = statement.where(ExternalSource.archived.is_(False))
    return list(db.scalars(statement))


@app.get("/api/v1/sources/{source_id}", response_model=SourceResponse, dependencies=[Depends(require_admin)])
def get_source(source_id: str, db: Session = Depends(get_db)) -> ExternalSource:
    return source_or_404(db, source_id)


@app.patch("/api/v1/sources/{source_id}", response_model=SourceResponse, dependencies=[Depends(require_admin)])
def update_source(source_id: str, payload: SourceUpdate, db: Session = Depends(get_db)) -> ExternalSource:
    source = source_or_404(db, source_id)
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(source, key, value)
    db.commit()
    db.refresh(source)
    return source


@app.delete("/api/v1/sources/{source_id}", response_model=SourceResponse, dependencies=[Depends(require_admin)])
def archive_source(source_id: str, db: Session = Depends(get_db)) -> ExternalSource:
    source = source_or_404(db, source_id)
    source.archived = True
    source.enabled = False
    source.status = "archived"
    db.commit()
    db.refresh(source)
    return source


@app.post("/api/v1/sources/{source_id}/ingest", response_model=IngestResponse, dependencies=[Depends(require_admin)])
def ingest_source(source_id: str, db: Session = Depends(get_db)) -> dict:
    source = source_or_404(db, source_id)
    job = run_ingestion(db, source)
    return {"job": job}


@app.get("/api/v1/ingestion/jobs", response_model=list[JobResponse], dependencies=[Depends(require_admin)])
def list_jobs(
    db: Session = Depends(get_db),
    source_id: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
) -> list[IngestionJob]:
    statement = select(IngestionJob).order_by(desc(IngestionJob.created_at)).limit(limit)
    if source_id:
        statement = statement.where(IngestionJob.source_id == source_id)
    return list(db.scalars(statement))


@app.get("/api/v1/ingestion/jobs/{job_id}", response_model=JobResponse, dependencies=[Depends(require_admin)])
def get_job(job_id: str, db: Session = Depends(get_db)) -> IngestionJob:
    job = db.get(IngestionJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")
    return job


@app.get("/api/v1/public/sources", response_model=list[PublicSource])
def public_sources(db: Session = Depends(get_db)) -> list[PublicSource]:
    sources = db.scalars(
        select(ExternalSource)
        .where(ExternalSource.enabled.is_(True), ExternalSource.archived.is_(False))
        .order_by(ExternalSource.name)
    )
    return [
        PublicSource(
            id=source.id,
            name=source.name,
            site_url=source.site_url,
            reliability_score=source.reliability_score,
            last_success_at=source.last_success_at,
        )
        for source in sources
    ]


@app.get("/api/v1/public/items", response_model=PublicItemsResponse)
def public_items(
    db: Session = Depends(get_db),
    source_id: str | None = None,
    limit: int = Query(default=25, ge=1, le=100),
) -> PublicItemsResponse:
    statement = select(NormalizedItem).order_by(desc(NormalizedItem.published_at), desc(NormalizedItem.created_at)).limit(limit)
    if source_id:
        statement = statement.where(NormalizedItem.source_id == source_id)
    items = list(db.scalars(statement))
    return PublicItemsResponse(items=[_public_item(item) for item in items], next_cursor=None)


@app.get("/api/v1/public/items/{item_id}", response_model=PublicItem)
def public_item(item_id: str, db: Session = Depends(get_db)) -> PublicItem:
    item = db.get(NormalizedItem, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found.")
    return _public_item(item)


@app.get("/api/v1/public/events", response_model=list[PublicEvent])
def public_events(
    db: Session = Depends(get_db),
    source_id: str | None = None,
    limit: int = Query(default=25, ge=1, le=100),
) -> list[EventCandidate]:
    statement = select(EventCandidate).order_by(desc(EventCandidate.created_at)).limit(limit)
    if source_id:
        statement = statement.where(EventCandidate.source_id == source_id)
    return list(db.scalars(statement))


@app.get("/api/v1/public/export.json")
def public_export(db: Session = Depends(get_db), source_id: str | None = None, limit: int = Query(default=100, ge=1, le=500)) -> dict:
    items = public_items(db=db, source_id=source_id, limit=limit)
    events = public_events(db=db, source_id=source_id, limit=limit)
    return {
        "items": [item.model_dump(mode="json") for item in items.items],
        "events": [PublicEvent.model_validate(event).model_dump(mode="json") for event in events],
    }


def _public_item(item: NormalizedItem) -> PublicItem:
    source = item.source
    return PublicItem(
        id=item.id,
        source=PublicSource(
            id=source.id,
            name=source.name,
            site_url=source.site_url,
            reliability_score=source.reliability_score,
            last_success_at=source.last_success_at,
        ),
        canonical_url=item.canonical_url,
        title=item.title,
        summary=item.summary,
        language=item.language,
        published_at=item.published_at,
        category_hints=item.category_hints,
        location_hints=item.location_hints,
        extraction_status=item.extraction_status,
    )
