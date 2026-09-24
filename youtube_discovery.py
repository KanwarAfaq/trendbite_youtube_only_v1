from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import Iterable

import requests

from config import settings

SEARCH_URL = "https://www.googleapis.com/youtube/v3/search"
VIDEOS_URL = "https://www.googleapis.com/youtube/v3/videos"


class YouTubeDiscoveryError(RuntimeError):
    pass


# Different modifiers are selected every 12-hour slot and every attempt. The
# themes stay broad, while the actual YouTube queries are generated live.
_QUERY_MODIFIERS = (
    "funny moments",
    "cute moments",
    "funny reaction",
    "laughing",
    "unexpected funny",
    "playing funny",
    "viral funny",
    "shorts funny",
    "best reaction",
    "adorable funny",
)

_THEME_ALIASES = {
    "animal": ("funny animals", "cute animals", "animal funny moments"),
    "cat": ("funny cat", "cute cat", "cat funny moments"),
    "dog": ("funny dog", "cute dog", "dog funny moments"),
    "baby": ("funny baby", "baby laughing", "baby funny reaction"),
    "monkey": ("funny monkey", "cute monkey", "monkey funny moments"),
    "little boss": ("little boss baby", "bossy baby", "baby acting like boss"),
}

_key_cursor = 0


def _key_label(index: int) -> str:
    return f"API#{index + 1}"


def _error_reasons(payload: object) -> set[str]:
    reasons: set[str] = set()
    if not isinstance(payload, dict):
        return reasons
    error = payload.get("error")
    if not isinstance(error, dict):
        return reasons
    for item in error.get("errors") or []:
        if isinstance(item, dict) and item.get("reason"):
            reasons.add(str(item["reason"]))
    if error.get("status"):
        reasons.add(str(error["status"]))
    return reasons


def _api_get(url: str, params: dict) -> dict:
    """GET from YouTube while rotating through configured API keys.

    Requests are distributed round-robin. If one key hits quota/rate/key errors,
    the same request is retried with the next configured key.
    """
    global _key_cursor

    keys = settings.youtube_api_keys
    if not keys:
        raise YouTubeDiscoveryError(
            "No YouTube API key configured. Set YOUTUBE_API_KEYS or YOUTUBE_API_KEY(_1/_2/_3)."
        )

    start = _key_cursor % len(keys)
    last_error = ""

    for offset in range(len(keys)):
        key_index = (start + offset) % len(keys)
        call_params = dict(params)
        call_params["key"] = keys[key_index]
        try:
            response = requests.get(url, params=call_params, timeout=30)
        except requests.RequestException as exc:
            last_error = f"{_key_label(key_index)} network error: {exc}"
            print(last_error)
            continue

        if response.ok:
            _key_cursor = (key_index + 1) % len(keys)
            return response.json()

        try:
            detail = response.json()
        except Exception:
            detail = response.text[:1000]
        reasons = _error_reasons(detail)
        last_error = f"{_key_label(key_index)} HTTP {response.status_code}: {detail}"

        # These errors are worth retrying with another key. For other errors we
        # still try the next key, but keep the full final diagnostic.
        if reasons & {
            "quotaExceeded",
            "dailyLimitExceeded",
            "rateLimitExceeded",
            "userRateLimitExceeded",
            "keyInvalid",
            "API_KEY_INVALID",
            "PERMISSION_DENIED",
            "RESOURCE_EXHAUSTED",
        }:
            print(f"{_key_label(key_index)} unavailable ({', '.join(sorted(reasons))}); rotating key")
        else:
            print(f"{_key_label(key_index)} request failed; trying next configured key")

    raise YouTubeDiscoveryError(last_error or "All configured YouTube API keys failed")


def parse_iso8601_duration(value: str | None) -> int | None:
    if not value:
        return None
    match = re.fullmatch(
        r"P(?:(?P<d>\d+)D)?(?:T(?:(?P<h>\d+)H)?(?:(?P<m>\d+)M)?(?:(?P<s>\d+)S)?)?",
        value,
    )
    if not match:
        return None
    return (
        int(match.group("d") or 0) * 86400
        + int(match.group("h") or 0) * 3600
        + int(match.group("m") or 0) * 60
        + int(match.group("s") or 0)
    )


def _duration_allowed(seconds: int | None) -> bool:
    if seconds is None:
        return True
    if settings.min_duration_seconds > 0 and seconds < settings.min_duration_seconds:
        return False
    if settings.max_duration_seconds > 0 and seconds > settings.max_duration_seconds:
        return False
    return True


def _license_is_reusable(license_name: str | None, channel_id: str | None) -> bool:
    if channel_id and channel_id in settings.youtube_allowed_channel_ids:
        return True
    if not settings.youtube_require_reusable_license:
        return True
    return (license_name or "").lower() == "creativecommon"


def _fresh_days(attempt: int) -> int:
    values: list[int] = []
    for raw in settings.discovery_fresh_days:
        try:
            value = int(raw)
        except (TypeError, ValueError):
            continue
        if value > 0:
            values.append(value)
    if not values:
        values = [7, 30, 90, 365, 1825]
    return values[min(max(1, attempt) - 1, len(values) - 1)]


def build_live_queries(attempt: int, now: datetime | None = None) -> tuple[str, ...]:
    """Generate search phrases for the current 12-hour slot and attempt.

    This removes the need for a long static DISCOVERY_QUERIES list while still
    keeping the requested subject areas explicit and controllable via
    DISCOVERY_THEMES.
    """
    now = now or datetime.now(timezone.utc)
    slot_hours = max(1, settings.discovery_slot_hours)
    slot = int(now.timestamp() // (slot_hours * 3600))

    themes = tuple(settings.discovery_themes) or ("animal", "cat", "dog", "baby", "monkey", "little boss")
    count = max(1, settings.discovery_queries_per_attempt)
    queries: list[str] = []

    for i in range(count):
        theme = themes[(slot + i) % len(themes)].strip().lower()
        aliases = _THEME_ALIASES.get(theme, (theme,))
        alias = aliases[(slot + attempt + i) % len(aliases)]
        modifier = _QUERY_MODIFIERS[(slot * 3 + attempt * 2 + i) % len(_QUERY_MODIFIERS)]

        # Avoid awkward duplication such as "funny cat funny moments".
        if "funny" in alias.lower() and modifier.startswith("funny"):
            modifier = _QUERY_MODIFIERS[(slot * 3 + attempt * 2 + i + 3) % len(_QUERY_MODIFIERS)]
        query = f"{alias} {modifier}".strip()
        if query not in queries:
            queries.append(query)

    return tuple(queries)


def _published_timestamp(value: str | None) -> float:
    if not value:
        return 0.0
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
    except (TypeError, ValueError):
        return 0.0


def discover(*, attempt: int = 1, queries: Iterable[str] | None = None, now: datetime | None = None) -> list[dict]:
    if not settings.youtube_api_enabled:
        raise YouTubeDiscoveryError("YOUTUBE_API_ENABLED=false. This bot requires the YouTube Data API.")
    if not settings.youtube_api_keys:
        raise YouTubeDiscoveryError(
            "No YouTube API key configured. Set YOUTUBE_API_KEYS or YOUTUBE_API_KEY(_1/_2/_3)."
        )

    now = now or datetime.now(timezone.utc)
    live_queries = tuple(queries or build_live_queries(attempt, now=now))
    fresh_days = _fresh_days(attempt)
    published_after = (now - timedelta(days=fresh_days)).replace(microsecond=0).isoformat().replace("+00:00", "Z")

    print(f"Live freshness window: last {fresh_days} day(s), publishedAfter={published_after}")
    print("Live queries:", " | ".join(live_queries))

    found_ids: list[str] = []
    seen: set[str] = set()
    snippet_by_id: dict[str, dict] = {}
    per_query = max(1, min(50, settings.discovery_results_per_query))

    for query in live_queries:
        params = {
            "part": "snippet",
            "type": "video",
            "q": query,
            "maxResults": per_query,
            "order": settings.youtube_order,
            "safeSearch": settings.youtube_safe_search,
            "publishedAfter": published_after,
        }
        if settings.youtube_relevance_language:
            params["relevanceLanguage"] = settings.youtube_relevance_language
        if settings.youtube_region_code:
            params["regionCode"] = settings.youtube_region_code
        if settings.youtube_video_license in {"creativeCommon", "youtube", "any"} and settings.youtube_video_license != "any":
            params["videoLicense"] = settings.youtube_video_license

        data = _api_get(SEARCH_URL, params)
        added = 0
        for item in data.get("items", []):
            video_id = ((item.get("id") or {}).get("videoId") or "").strip()
            if not video_id or video_id in seen:
                continue
            seen.add(video_id)
            found_ids.append(video_id)
            snippet_by_id[video_id] = item.get("snippet") or {}
            added += 1
        print(f"YouTube live search: '{query}' -> {added} new IDs")

    if not found_ids:
        return []

    details: list[dict] = []
    for start in range(0, len(found_ids), 50):
        batch = found_ids[start:start + 50]
        data = _api_get(
            VIDEOS_URL,
            {
                "part": "snippet,contentDetails,statistics,status",
                "id": ",".join(batch),
                "maxResults": 50,
            },
        )
        details.extend(data.get("items", []))

    candidates: list[dict] = []
    for item in details:
        video_id = str(item.get("id") or "")
        snippet = item.get("snippet") or snippet_by_id.get(video_id) or {}
        content = item.get("contentDetails") or {}
        stats = item.get("statistics") or {}
        status = item.get("status") or {}
        duration = parse_iso8601_duration(content.get("duration"))
        if not _duration_allowed(duration):
            continue
        if status.get("uploadStatus") not in {None, "processed"}:
            continue

        license_name = status.get("license")
        channel_id = snippet.get("channelId")
        if not _license_is_reusable(license_name, channel_id):
            continue

        published = snippet.get("publishedAt")
        candidates.append({
            "source_url": f"https://www.youtube.com/watch?v={video_id}",
            "source_platform": "youtube",
            "source_content_id": video_id,
            "source_author": snippet.get("channelTitle"),
            "source_author_id": channel_id,
            "title": snippet.get("title"),
            "description": snippet.get("description"),
            "duration_seconds": duration,
            "source_published_at": published,
            "source_license": license_name,
            "view_count": int(stats.get("viewCount") or 0),
            "like_count": int(stats.get("likeCount") or 0),
            "width": None,
            "height": None,
        })

    # Freshness is primary; views/likes break ties among similarly recent videos.
    candidates.sort(
        key=lambda item: (
            _published_timestamp(item.get("source_published_at")),
            item.get("view_count") or 0,
            item.get("like_count") or 0,
        ),
        reverse=True,
    )
    if settings.discovery_max_candidates > 0:
        candidates = candidates[: settings.discovery_max_candidates]
    print(f"YouTube reusable live candidates: {len(candidates)}")
    return candidates
