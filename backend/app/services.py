from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.feed_utils import (
    FeedError,
    discover_feeds_from_html,
    extract_category_hints,
    extract_location_hints,
    item_hash,
    parse_feed_bytes,
    safe_fetch,
)
from app.models import EventCandidate, ExternalSource, IngestionJob, NormalizedItem, RawFetchedItem


def detect_source(url: str, fetch_sample_items: bool = True) -> dict:
    warnings: list[str] = []
    fetch = safe_fetch(url)
    candidates: list[dict] = []

    try:
        parsed = parse_feed_bytes(fetch.body, fetch.url)
        candidates.append(_candidate_from_parsed(parsed, fetch.url, fetch_sample_items, warnings))
    except FeedError:
        title, links = discover_feeds_from_html(fetch.body, fetch.url)
        if not links:
            raise FeedError("No RSS or Atom feed was found at this URL.")
        for link in links[:5]:
            try:
                linked_fetch = safe_fetch(link)
                parsed = parse_feed_bytes(linked_fetch.body, linked_fetch.url)
                candidate = _candidate_from_parsed(parsed, linked_fetch.url, fetch_sample_items, [])
                candidate["score"] -= 0.05
                if not candidate.get("title"):
                    candidate["title"] = title
                candidates.append(candidate)
            except FeedError as exc:
                warnings.append(f"Skipped discovered feed {link}: {exc}")

    if not candidates:
        raise FeedError("Feed candidates were discovered, but none could be parsed.")
    candidates.sort(key=lambda item: item["score"], reverse=True)
    return {"input_url": url, "status": "detected", "candidates": candidates, "warnings": warnings}


def _candidate_from_parsed(parsed: dict, feed_url: str, include_items: bool, warnings: list[str]) -> dict:
    items = parsed["items"][:5] if include_items else []
    score = 0.55
    if parsed.get("title"):
        score += 0.1
    if parsed.get("site_url"):
        score += 0.1
    if items:
        score += 0.15
    if any(item.get("published_at") for item in items):
        score += 0.1
    return {
        "feed_url": feed_url,
        "feed_type": parsed["feed_type"],
        "title": parsed.get("title"),
        "site_url": parsed.get("site_url"),
        "language": parsed.get("language"),
        "score": min(round(score, 2), 1.0),
        "latest_items": [
            {"title": item.get("title"), "url": item.get("url"), "published_at": item.get("published_at")}
            for item in items
        ],
        "warnings": warnings,
    }


def create_source(db: Session, payload) -> ExternalSource:
    detected = detect_source(str(payload.feed_url), fetch_sample_items=True)
    best = detected["candidates"][0]
    source = ExternalSource(
        name=payload.name or best.get("title") or str(payload.feed_url),
        feed_url=best["feed_url"],
        site_url=best.get("site_url"),
        detected_title=best.get("title"),
        detected_feed_type=best.get("feed_type"),
        detected_language=best.get("language"),
        fetch_interval_minutes=payload.fetch_interval_minutes,
        reliability_score=payload.reliability_score,
        enabled=payload.enabled,
        category_scope=payload.category_scope,
        country_scope=payload.country_scope,
    )
    db.add(source)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise FeedError("This feed URL already exists as a source.") from exc
    db.refresh(source)
    return source


def run_ingestion(db: Session, source: ExternalSource, trigger_type: str = "manual") -> IngestionJob:
    job = IngestionJob(source_id=source.id, trigger_type=trigger_type, status="running", started_at=datetime.now(timezone.utc))
    db.add(job)
    db.commit()
    db.refresh(job)

    try:
        fetched = safe_fetch(source.feed_url, source.etag, source.last_modified)
        if fetched.body == b"":
            job.status = "success"
            job.finished_at = datetime.now(timezone.utc)
            source.last_success_at = job.finished_at
            db.commit()
            db.refresh(job)
            return job
        parsed = parse_feed_bytes(fetched.body, fetched.url)
        source.etag = fetched.etag
        source.last_modified = fetched.last_modified
        source.detected_title = source.detected_title or parsed.get("title")
        source.detected_feed_type = parsed.get("feed_type")
        source.detected_language = source.detected_language or parsed.get("language")
        source.site_url = source.site_url or parsed.get("site_url")

        for item in parsed["items"]:
            job.fetched_count += 1
            content_hash = item_hash(item)
            exists = db.scalar(
                select(RawFetchedItem).where(
                    RawFetchedItem.source_id == source.id,
                    RawFetchedItem.content_hash == content_hash,
                )
            )
            if exists:
                job.duplicate_raw_count += 1
                continue
            raw = RawFetchedItem(
                source_id=source.id,
                job_id=job.id,
                source_item_id=item.get("id"),
                source_url=item.get("url"),
                title=item.get("title"),
                raw_payload=_jsonable_item(item),
                content_hash=content_hash,
                published_at=item.get("published_at"),
            )
            db.add(raw)
            db.flush()

            title = item.get("title") or "Untitled feed item"
            summary = item.get("summary")
            text = " ".join(part for part in [title, summary or ""] if part)
            category_hints = list(dict.fromkeys((item.get("categories") or []) + extract_category_hints(text)))
            location_hints = extract_location_hints(text)
            normalized = NormalizedItem(
                raw_item_id=raw.id,
                source_id=source.id,
                canonical_url=item.get("url"),
                title=title,
                summary=summary,
                body=summary,
                language=source.detected_language,
                published_at=item.get("published_at"),
                category_hints=category_hints,
                location_hints=location_hints,
            )
            db.add(normalized)
            db.flush()
            job.normalized_count += 1

            candidate = EventCandidate(
                normalized_item_id=normalized.id,
                source_id=source.id,
                title=title,
                summary=summary,
                category_hints=category_hints,
                location_hints=location_hints,
                risk_hint=_risk_hint(category_hints),
            )
            db.add(candidate)
            job.event_candidate_count += 1

        job.status = "success"
        source.status = "active"
        source.last_error = None
        source.last_success_at = datetime.now(timezone.utc)
    except Exception as exc:
        job.status = "failed"
        job.error_message = str(exc)
        source.status = "failing"
        source.last_error = str(exc)
        source.last_failure_at = datetime.now(timezone.utc)
    finally:
        job.finished_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(job)
    return job


def _risk_hint(categories: list[str]) -> str:
    if "conflict" in categories or "cyber" in categories:
        return "medium"
    if "natural_disaster" in categories:
        return "medium"
    return "unknown"


def _jsonable_item(item: dict) -> dict:
    clean = dict(item)
    published_at = clean.get("published_at")
    if published_at is not None:
        clean["published_at"] = published_at.isoformat()
    return clean
