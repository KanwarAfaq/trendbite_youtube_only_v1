import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()


def env_bool(name: str, default: bool = False) -> bool:
    return os.getenv(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


def env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)).strip())
    except (TypeError, ValueError):
        return default


def env_list(name: str, default: str = "", sep: str = "|") -> tuple[str, ...]:
    raw = os.getenv(name, default)
    return tuple(x.strip() for x in raw.split(sep) if x.strip())


def youtube_api_keys() -> tuple[str, ...]:
    """Collect YouTube API keys without exposing them in logs.

    Supports either:
      YOUTUBE_API_KEYS=key1|key2|key3
    or the backwards-compatible individual variables:
      YOUTUBE_API_KEY, YOUTUBE_API_KEY_1, YOUTUBE_API_KEY_2, YOUTUBE_API_KEY_3
    Duplicate values are removed while preserving order.
    """
    values: list[str] = list(env_list("YOUTUBE_API_KEYS", ""))
    for name in ("YOUTUBE_API_KEY", "YOUTUBE_API_KEY_1", "YOUTUBE_API_KEY_2", "YOUTUBE_API_KEY_3"):
        value = os.getenv(name, "").strip()
        if value:
            values.append(value)

    seen: set[str] = set()
    unique: list[str] = []
    for value in values:
        if value and value not in seen:
            seen.add(value)
            unique.append(value)
    return tuple(unique)


@dataclass(frozen=True)
class Settings:
    # YouTube live discovery
    youtube_api_keys: tuple[str, ...] = youtube_api_keys()
    youtube_api_enabled: bool = env_bool("YOUTUBE_API_ENABLED", True)
    discovery_themes: tuple[str, ...] = env_list(
        "DISCOVERY_THEMES",
        "animal|cat|dog|baby|monkey|little boss",
    )
    discovery_queries_per_attempt: int = env_int("DISCOVERY_QUERIES_PER_ATTEMPT", 6)
    discovery_results_per_query: int = env_int("DISCOVERY_RESULTS_PER_QUERY", 25)
    discovery_max_candidates: int = env_int("DISCOVERY_MAX_CANDIDATES", 120)
    # Fresh-first search. Each later attempt widens the upload-age window.
    discovery_fresh_days: tuple[str, ...] = env_list("DISCOVERY_FRESH_DAYS", "7|30|90|365|1825")
    discovery_slot_hours: int = env_int("DISCOVERY_SLOT_HOURS", 12)

    youtube_order: str = os.getenv("YOUTUBE_SEARCH_ORDER", "date").strip() or "date"
    youtube_region_code: str = os.getenv("YOUTUBE_REGION_CODE", "").strip()
    youtube_relevance_language: str = os.getenv("YOUTUBE_RELEVANCE_LANGUAGE", "en").strip()
    youtube_safe_search: str = os.getenv("YOUTUBE_SAFE_SEARCH", "none").strip() or "none"

    # Reposting safety: Creative Commons by default.
    youtube_video_license: str = os.getenv("YOUTUBE_VIDEO_LICENSE", "creativeCommon").strip() or "creativeCommon"
    youtube_require_reusable_license: bool = env_bool("YOUTUBE_REQUIRE_REUSABLE_LICENSE", True)
    youtube_allowed_channel_ids: tuple[str, ...] = env_list("YOUTUBE_ALLOWED_CHANNEL_IDS", "")

    # 0 = no duration restriction. For Facebook Reels, a practical value such as
    # 180 can be set in .env if desired.
    min_duration_seconds: int = env_int("DISCOVERY_MIN_DURATION", 0)
    max_duration_seconds: int = env_int("DISCOVERY_MAX_DURATION", 0)

    # Batch controls: target ten successful Facebook posts per run.
    video_post_count: int = env_int("VIDEO_POST_COUNT", 10)
    video_post_delay_seconds: int = env_int("VIDEO_POST_DELAY_SECONDS", 60)
    video_max_attempts: int = env_int("VIDEO_MAX_ATTEMPTS", 5)

    # Local/download
    download_dir: str = os.getenv("DOWNLOAD_DIR", "videos")
    delete_local_after_post: bool = env_bool("DELETE_LOCAL_AFTER_POST", True)
    ytdlp_cookies_from_browser: str = os.getenv("YTDLP_COOKIES_FROM_BROWSER", "").strip()
    ytdlp_cookie_file: str = os.getenv("YTDLP_COOKIE_FILE", "").strip()

    # Supabase duplicate/history
    supabase_url: str = os.getenv("SUPABASE_URL", "").strip()
    supabase_key: str = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()

    # Facebook
    facebook_graph_version: str = os.getenv("FACEBOOK_GRAPH_VERSION", "v26.0").strip() or "v26.0"
    facebook_page_id: str = os.getenv("FACEBOOK_PAGE_ID", "").strip()
    facebook_page_access_token: str = os.getenv("FACEBOOK_PAGE_ACCESS_TOKEN", "").strip()
    facebook_publish_mode: str = os.getenv("FACEBOOK_PUBLISH_MODE", "reel").strip().lower() or "reel"


settings = Settings()
