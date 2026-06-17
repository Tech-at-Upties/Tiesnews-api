from __future__ import annotations

import hashlib
import html
import ipaddress
import re
import socket
from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlparse
from urllib.request import Request, build_opener
from urllib.request import HTTPRedirectHandler
from xml.etree import ElementTree

from app.config import get_settings


class FeedError(ValueError):
    pass


class NoRedirectHandler(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # type: ignore[no-untyped-def]
        return None


@dataclass
class FetchResult:
    url: str
    content_type: str
    body: bytes
    etag: str | None
    last_modified: str | None


class FeedLinkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[str] = []
        self.title: str | None = None
        self._in_title = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_dict = {key.lower(): value or "" for key, value in attrs}
        if tag.lower() == "title":
            self._in_title = True
        if tag.lower() != "link":
            return
        rel = attrs_dict.get("rel", "").lower()
        type_ = attrs_dict.get("type", "").lower()
        href = attrs_dict.get("href")
        if href and "alternate" in rel and ("rss" in type_ or "atom" in type_ or "xml" in type_):
            self.links.append(href)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "title":
            self._in_title = False

    def handle_data(self, data: str) -> None:
        if self._in_title and data.strip():
            self.title = data.strip()


def validate_public_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise FeedError("Only http and https URLs are supported.")
    if not parsed.hostname:
        raise FeedError("URL must include a hostname.")
    if parsed.hostname.lower() in {"localhost", "localhost.localdomain"}:
        raise FeedError("Localhost URLs are blocked for source fetching.")
    try:
        addresses = socket.getaddrinfo(parsed.hostname, None)
    except socket.gaierror as exc:
        raise FeedError(f"Could not resolve hostname: {parsed.hostname}") from exc
    for address in addresses:
        ip = ipaddress.ip_address(address[4][0])
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_multicast or ip.is_reserved:
            raise FeedError("URL resolves to a blocked private or reserved network.")


def safe_fetch(url: str, etag: str | None = None, last_modified: str | None = None) -> FetchResult:
    settings = get_settings()
    current_url = url
    opener = build_opener(NoRedirectHandler)
    headers = {"User-Agent": settings.user_agent}
    if etag:
        headers["If-None-Match"] = etag
    if last_modified:
        headers["If-Modified-Since"] = last_modified

    for _ in range(5):
        validate_public_url(current_url)
        request = Request(current_url, headers=headers)
        try:
            response = opener.open(request, timeout=settings.fetch_timeout_seconds)
        except HTTPError as exc:
            if exc.code in {301, 302, 303, 307, 308} and exc.headers.get("Location"):
                current_url = urljoin(current_url, exc.headers["Location"])
                continue
            if exc.code == 304:
                return FetchResult(current_url, exc.headers.get("content-type", ""), b"", exc.headers.get("etag"), exc.headers.get("last-modified"))
            raise FeedError(f"Source returned HTTP {exc.code}.") from exc
        except URLError as exc:
            raise FeedError(f"Could not fetch URL: {exc.reason}") from exc

        body = response.read(settings.max_feed_bytes + 1)
        if len(body) > settings.max_feed_bytes:
            raise FeedError("Response is larger than the configured feed size limit.")
        final_url = response.geturl()
        validate_public_url(final_url)
        return FetchResult(
            final_url,
            response.headers.get("content-type", ""),
            body,
            response.headers.get("etag"),
            response.headers.get("last-modified"),
        )
    raise FeedError("Too many redirects while fetching source.")


def strip_text(value: str | None) -> str | None:
    if not value:
        return None
    text = re.sub(r"<[^>]+>", " ", value)
    text = html.unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    return text or None


def parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        dt = parsedate_to_datetime(value)
    except (TypeError, ValueError):
        try:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _text(node: ElementTree.Element | None) -> str | None:
    if node is None or node.text is None:
        return None
    return strip_text(node.text)


def _find_child(node: ElementTree.Element, names: list[str]) -> ElementTree.Element | None:
    for child in node:
        clean = child.tag.split("}", 1)[-1].lower()
        if clean in names:
            return child
    return None


def _find_text(node: ElementTree.Element, names: list[str]) -> str | None:
    return _text(_find_child(node, names))


def parse_feed_bytes(body: bytes, feed_url: str) -> dict[str, Any]:
    try:
        root = ElementTree.fromstring(body)
    except ElementTree.ParseError as exc:
        raise FeedError("The URL did not return parseable RSS or Atom XML.") from exc

    root_name = root.tag.split("}", 1)[-1].lower()
    if root_name == "rss":
        return _parse_rss(root, feed_url)
    if root_name == "feed":
        return _parse_atom(root, feed_url)
    if root_name == "rdf":
        return _parse_rss(root, feed_url)
    raise FeedError("The XML document is not an RSS or Atom feed.")


def _parse_rss(root: ElementTree.Element, feed_url: str) -> dict[str, Any]:
    channel = root.find("channel") or _find_child(root, ["channel"]) or root
    items = []
    for item in channel.iter():
        if item.tag.split("}", 1)[-1].lower() != "item":
            continue
        guid = _find_text(item, ["guid", "id"])
        link = _find_text(item, ["link"])
        title = _find_text(item, ["title"])
        summary = _find_text(item, ["description", "summary"])
        published = _find_text(item, ["pubdate", "published", "updated", "date"])
        categories = [_text(child) for child in item if child.tag.split("}", 1)[-1].lower() == "category"]
        items.append(
            {
                "id": guid or link or title,
                "url": link,
                "title": title,
                "summary": summary,
                "published_at": parse_dt(published),
                "categories": [category for category in categories if category],
                "raw": {child.tag.split('}', 1)[-1]: child.text for child in item},
            }
        )
    return {
        "feed_type": "rss",
        "feed_url": feed_url,
        "title": _find_text(channel, ["title"]),
        "site_url": _find_text(channel, ["link"]),
        "language": _find_text(channel, ["language"]),
        "items": items,
    }


def _parse_atom(root: ElementTree.Element, feed_url: str) -> dict[str, Any]:
    items = []
    site_url = None
    for link in root:
        if link.tag.split("}", 1)[-1].lower() == "link":
            rel = link.attrib.get("rel", "alternate")
            if rel == "alternate":
                site_url = link.attrib.get("href")
                break
    for entry in root.iter():
        if entry.tag.split("}", 1)[-1].lower() != "entry":
            continue
        link_url = None
        for child in entry:
            if child.tag.split("}", 1)[-1].lower() == "link" and child.attrib.get("href"):
                link_url = child.attrib["href"]
                break
        categories = [
            child.attrib.get("term")
            for child in entry
            if child.tag.split("}", 1)[-1].lower() == "category" and child.attrib.get("term")
        ]
        items.append(
            {
                "id": _find_text(entry, ["id"]) or link_url or _find_text(entry, ["title"]),
                "url": link_url,
                "title": _find_text(entry, ["title"]),
                "summary": _find_text(entry, ["summary", "content"]),
                "published_at": parse_dt(_find_text(entry, ["published", "updated"])),
                "categories": categories,
                "raw": {child.tag.split('}', 1)[-1]: child.text for child in entry},
            }
        )
    return {
        "feed_type": "atom",
        "feed_url": feed_url,
        "title": _find_text(root, ["title"]),
        "site_url": site_url,
        "language": root.attrib.get("{http://www.w3.org/XML/1998/namespace}lang"),
        "items": items,
    }


def discover_feeds_from_html(body: bytes, base_url: str) -> tuple[str | None, list[str]]:
    parser = FeedLinkParser()
    parser.feed(body.decode("utf-8", errors="ignore"))
    return parser.title, [urljoin(base_url, link) for link in parser.links]


def item_hash(item: dict[str, Any]) -> str:
    seed = "|".join(str(item.get(key) or "") for key in ["id", "url", "title", "summary"])
    return hashlib.sha256(seed.encode("utf-8")).hexdigest()


COUNTRY_HINTS = {
    "Ukraine": {"country_code": "UA", "latitude": 48.3794, "longitude": 31.1656},
    "Russia": {"country_code": "RU", "latitude": 61.524, "longitude": 105.3188},
    "India": {"country_code": "IN", "latitude": 20.5937, "longitude": 78.9629},
    "Nepal": {"country_code": "NP", "latitude": 28.3949, "longitude": 84.124},
    "Israel": {"country_code": "IL", "latitude": 31.0461, "longitude": 34.8516},
    "Gaza": {"country_code": "PS", "latitude": 31.5017, "longitude": 34.4668},
    "Syria": {"country_code": "SY", "latitude": 34.8021, "longitude": 38.9968},
    "Iran": {"country_code": "IR", "latitude": 32.4279, "longitude": 53.688},
    "China": {"country_code": "CN", "latitude": 35.8617, "longitude": 104.1954},
    "United States": {"country_code": "US", "latitude": 37.0902, "longitude": -95.7129},
}

CATEGORY_KEYWORDS = {
    "conflict": ["war", "attack", "strike", "shelling", "military", "border"],
    "humanitarian": ["refugee", "aid", "relief", "displaced", "famine"],
    "natural_disaster": ["earthquake", "flood", "storm", "wildfire", "landslide"],
    "infrastructure": ["power", "bridge", "port", "airport", "rail", "road"],
    "cyber": ["cyber", "hack", "malware", "ransomware", "breach"],
}


def extract_location_hints(text: str) -> list[dict[str, Any]]:
    hints = []
    lowered = text.lower()
    for name, data in COUNTRY_HINTS.items():
        if name.lower() in lowered:
            hints.append({"name": name, "confidence": 0.72, **data})
    return hints


def extract_category_hints(text: str) -> list[str]:
    lowered = text.lower()
    categories = []
    for category, words in CATEGORY_KEYWORDS.items():
        if any(word in lowered for word in words):
            categories.append(category)
    return categories
