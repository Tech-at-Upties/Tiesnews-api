from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, JSON, String, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def new_id() -> str:
    return str(uuid4())


class ExternalSource(Base):
    __tablename__ = "external_sources"

    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    connector_type: Mapped[str] = mapped_column(String(32), nullable=False, default="rss")
    feed_url: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    site_url: Mapped[str | None] = mapped_column(Text)
    detected_title: Mapped[str | None] = mapped_column(String(255))
    detected_feed_type: Mapped[str | None] = mapped_column(String(32))
    detected_language: Mapped[str | None] = mapped_column(String(32))
    fetch_interval_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=30)
    reliability_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.7)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    archived: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")
    category_scope: Mapped[list[str] | None] = mapped_column(JSON)
    country_scope: Mapped[str | None] = mapped_column(String(16))
    etag: Mapped[str | None] = mapped_column(String(255))
    last_modified: Mapped[str | None] = mapped_column(String(255))
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_failure_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    jobs: Mapped[list["IngestionJob"]] = relationship(back_populates="source")
    raw_items: Mapped[list["RawFetchedItem"]] = relationship(back_populates="source")
    normalized_items: Mapped[list["NormalizedItem"]] = relationship(back_populates="source")


class IngestionJob(Base):
    __tablename__ = "ingestion_jobs"

    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True, default=new_id)
    source_id: Mapped[str] = mapped_column(Uuid(as_uuid=False), ForeignKey("external_sources.id"), nullable=False)
    trigger_type: Mapped[str] = mapped_column(String(32), nullable=False, default="manual")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="queued")
    fetched_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    duplicate_raw_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    normalized_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    event_candidate_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_message: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    source: Mapped[ExternalSource] = relationship(back_populates="jobs")


class RawFetchedItem(Base):
    __tablename__ = "raw_fetched_items"
    __table_args__ = (
        UniqueConstraint("source_id", "source_item_id", name="uq_raw_source_item_id"),
        UniqueConstraint("source_id", "content_hash", name="uq_raw_source_hash"),
    )

    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True, default=new_id)
    source_id: Mapped[str] = mapped_column(Uuid(as_uuid=False), ForeignKey("external_sources.id"), nullable=False)
    job_id: Mapped[str] = mapped_column(Uuid(as_uuid=False), ForeignKey("ingestion_jobs.id"), nullable=False)
    source_item_id: Mapped[str | None] = mapped_column(Text)
    source_url: Mapped[str | None] = mapped_column(Text)
    title: Mapped[str | None] = mapped_column(Text)
    raw_payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    processing_status: Mapped[str] = mapped_column(String(32), default="stored", nullable=False)

    source: Mapped[ExternalSource] = relationship(back_populates="raw_items")


class NormalizedItem(Base):
    __tablename__ = "normalized_items"

    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True, default=new_id)
    raw_item_id: Mapped[str] = mapped_column(Uuid(as_uuid=False), ForeignKey("raw_fetched_items.id"), nullable=False)
    source_id: Mapped[str] = mapped_column(Uuid(as_uuid=False), ForeignKey("external_sources.id"), nullable=False)
    canonical_url: Mapped[str | None] = mapped_column(Text)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    summary: Mapped[str | None] = mapped_column(Text)
    body: Mapped[str | None] = mapped_column(Text)
    language: Mapped[str | None] = mapped_column(String(32))
    image_url: Mapped[str | None] = mapped_column(Text)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    category_hints: Mapped[list[str] | None] = mapped_column(JSON)
    location_hints: Mapped[list[dict] | None] = mapped_column(JSON)
    extraction_status: Mapped[str] = mapped_column(String(32), nullable=False, default="processed")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    source: Mapped[ExternalSource] = relationship(back_populates="normalized_items")


class EventCandidate(Base):
    __tablename__ = "event_candidates"

    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True, default=new_id)
    normalized_item_id: Mapped[str] = mapped_column(Uuid(as_uuid=False), ForeignKey("normalized_items.id"), nullable=False)
    source_id: Mapped[str] = mapped_column(Uuid(as_uuid=False), ForeignKey("external_sources.id"), nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    summary: Mapped[str | None] = mapped_column(Text)
    category_hints: Mapped[list[str] | None] = mapped_column(JSON)
    location_hints: Mapped[list[dict] | None] = mapped_column(JSON)
    risk_hint: Mapped[str] = mapped_column(String(32), nullable=False, default="unknown")
    publication_status: Mapped[str] = mapped_column(String(32), nullable=False, default="api_visible")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class AdminApiKey(Base):
    __tablename__ = "admin_api_keys"

    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    key_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
