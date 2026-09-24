from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from supabase import Client, create_client

from config import settings


class SupabaseStore:
    def __init__(self):
        if not settings.supabase_url or not settings.supabase_key:
            raise RuntimeError("SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY not configured")
        self.db: Client = create_client(settings.supabase_url, settings.supabase_key)

    def find_by_source_url(self, source_url: str):
        res = self.db.table("content_items").select("*").eq("source_url", source_url).limit(1).execute()
        return res.data[0] if res.data else None

    def find_by_source_identity(self, platform: str, content_id: str):
        res = (
            self.db.table("content_items")
            .select("*")
            .eq("source_platform", platform)
            .eq("source_content_id", content_id)
            .limit(1)
            .execute()
        )
        return res.data[0] if res.data else None

    def create_candidate(self, metadata: dict[str, Any], rights_status: str = "licensed") -> dict[str, Any]:
        payload = {
            "source_url": metadata["source_url"],
            "source_platform": "youtube",
            "source_content_id": metadata.get("source_content_id"),
            "source_author": metadata.get("source_author"),
            "source_author_id": metadata.get("source_author_id"),
            "title": metadata.get("title"),
            "source_description": metadata.get("description"),
            "duration_seconds": metadata.get("duration_seconds"),
            "source_published_at": metadata.get("source_published_at"),
            "rights_status": rights_status,
            "discovered_by": "youtube_only",
            "status": "discovered",
            "raw_metadata": metadata,
        }
        res = self.db.table("content_items").insert(payload).execute()
        return res.data[0]

    def update_status(self, content_id: str, status: str, error_message: str | None = None):
        self.db.table("content_items").update({
            "status": status,
            "last_error": error_message,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }).eq("id", content_id).execute()

    def save_download_metadata(self, content_id: str, sha256: str):
        self.db.table("content_items").update({
            "file_sha256": sha256,
            "status": "downloaded",
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }).eq("id", content_id).execute()

    def already_posted_hash(self, sha256: str) -> bool:
        res = (
            self.db.table("content_items")
            .select("id")
            .eq("file_sha256", sha256)
            .eq("status", "posted")
            .limit(1)
            .execute()
        )
        return bool(res.data)

    def record_facebook_post(self, *, content_id: str, facebook_video_id: str | None, caption: str, status: str, raw_response: dict | None = None, error_message: str | None = None):
        self.db.table("facebook_posts").insert({
            "content_id": content_id,
            "page_id": settings.facebook_page_id,
            "publish_mode": settings.facebook_publish_mode,
            "facebook_video_id": facebook_video_id,
            "caption": caption,
            "status": status,
            "raw_response": raw_response or {},
            "error_message": error_message,
        }).execute()
