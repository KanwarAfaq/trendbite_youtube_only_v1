from __future__ import annotations

import os
from typing import Any

import requests

from config import settings


class FacebookPublishError(RuntimeError):
    pass


class FacebookPublisher:
    def __init__(self):
        self.version = settings.facebook_graph_version
        self.page_id = settings.facebook_page_id
        self.token = settings.facebook_page_access_token
        if not self.page_id or not self.token:
            raise FacebookPublishError("FACEBOOK_PAGE_ID / FACEBOOK_PAGE_ACCESS_TOKEN are not configured")

    @staticmethod
    def _raise(response: requests.Response):
        if response.ok:
            return
        try:
            detail = response.json()
        except Exception:
            detail = response.text[:1200]
        raise FacebookPublishError(f"Facebook HTTP {response.status_code}: {detail}")

    def validate_page_token(self) -> dict[str, Any]:
        url = f"https://graph.facebook.com/{self.version}/{self.page_id}"
        r = requests.get(
            url,
            params={"access_token": self.token, "fields": "id,name"},
            timeout=30,
        )
        self._raise(r)
        return r.json()

    def publish_regular_video(self, video_path: str, caption: str, title: str | None = None) -> dict[str, Any]:
        url = f"https://graph-video.facebook.com/{self.version}/{self.page_id}/videos"
        with open(video_path, "rb") as f:
            files = {"source": (os.path.basename(video_path), f, "video/mp4")}
            data = {
                "access_token": self.token,
                "description": caption,
                "published": "true",
            }
            if title:
                data["title"] = title[:255]
            r = requests.post(url, files=files, data=data, timeout=600)
        self._raise(r)
        return r.json()

    def publish_reel(self, video_path: str, caption: str, title: str | None = None) -> dict[str, Any]:
        start_url = f"https://graph.facebook.com/{self.version}/{self.page_id}/video_reels"
        start = requests.post(
            start_url,
            params={"access_token": self.token, "upload_phase": "start"},
            timeout=60,
        )
        self._raise(start)
        session = start.json()
        video_id = session["video_id"]
        upload_url = session["upload_url"]

        file_size = os.path.getsize(video_path)
        with open(video_path, "rb") as f:
            upload = requests.post(
                upload_url,
                headers={
                    "Authorization": f"OAuth {self.token}",
                    "offset": "0",
                    "file_size": str(file_size),
                    "Content-Type": "application/octet-stream",
                },
                data=f,
                timeout=600,
            )
        self._raise(upload)

        finish_params = {
            "access_token": self.token,
            "upload_phase": "finish",
            "video_id": video_id,
            "video_state": "PUBLISHED",
            "description": caption,
        }
        if title:
            finish_params["title"] = title[:255]

        finish = requests.post(start_url, params=finish_params, timeout=60)
        self._raise(finish)
        result = finish.json()
        result["video_id"] = video_id
        return result

    def publish_photo(self, image_path: str, caption: str) -> dict[str, Any]:
        """Publish a Page photo with a long caption/article body."""
        url = f"https://graph.facebook.com/{self.version}/{self.page_id}/photos"
        with open(image_path, "rb") as f:
            files = {"source": (os.path.basename(image_path), f)}
            data = {
                "access_token": self.token,
                "caption": caption,
                "published": "true",
            }
            r = requests.post(url, files=files, data=data, timeout=300)
        self._raise(r)
        return r.json()

    def publish_link_post(self, message: str, link: str) -> dict[str, Any]:
        """Fallback article post; Facebook may render the source link preview."""
        url = f"https://graph.facebook.com/{self.version}/{self.page_id}/feed"
        r = requests.post(
            url,
            data={
                "access_token": self.token,
                "message": message,
                "link": link,
            },
            timeout=90,
        )
        self._raise(r)
        return r.json()
