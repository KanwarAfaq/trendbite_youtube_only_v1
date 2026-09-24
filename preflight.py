from config import settings

checks = {
    "YOUTUBE_API_ENABLED": settings.youtube_api_enabled,
    "YOUTUBE_API_KEYS": len(settings.youtube_api_keys) > 0,
    "FACEBOOK_PAGE_ID": bool(settings.facebook_page_id),
    "FACEBOOK_PAGE_ACCESS_TOKEN": bool(settings.facebook_page_access_token),
    "SUPABASE_URL": bool(settings.supabase_url),
    "SUPABASE_SERVICE_ROLE_KEY": bool(settings.supabase_key),
}

print("TrendBite LIVE discovery preflight")
for key, value in checks.items():
    print(f"{key}: {'OK' if value else 'MISSING/OFF'}")
print("YouTube API key count:", len(settings.youtube_api_keys))
print("Themes:", " | ".join(settings.discovery_themes))
print("Queries per attempt:", settings.discovery_queries_per_attempt)
print("Freshness windows (days):", " | ".join(settings.discovery_fresh_days))
print("Post target:", settings.video_post_count)
print("Delay seconds:", settings.video_post_delay_seconds)
print("License filter:", settings.youtube_video_license)

if not all(checks.values()):
    raise SystemExit(1)
