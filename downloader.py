from __future__ import annotations

import hashlib
import os
import re
from pathlib import Path

import yt_dlp

from config import settings


class DownloadError(RuntimeError):
    pass


def _browser_spec(spec: str):
    # Simple browser/profile support: edge or chrome or firefox[:profile]
    spec = spec.strip()
    if not spec:
        return None
    if ":" in spec:
        name, profile = spec.split(":", 1)
        return (name.strip().lower(), profile.strip() or None, None, None)
    return (spec.lower(), None, None, None)


def _auth_options() -> dict:
    if settings.ytdlp_cookie_file and os.path.exists(settings.ytdlp_cookie_file):
        return {"cookiefile": settings.ytdlp_cookie_file}
    browser = _browser_spec(settings.ytdlp_cookies_from_browser)
    if browser:
        return {"cookiesfrombrowser": browser}
    return {}


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def download_youtube(url: str) -> tuple[str, dict, str]:
    Path(settings.download_dir).mkdir(parents=True, exist_ok=True)
    outtmpl = os.path.join(settings.download_dir, "%(id)s.%(ext)s")
    opts = {
        "format": "bestvideo[height<=1080]+bestaudio/best[height<=1080]/best",
        "merge_output_format": "mp4",
        "outtmpl": outtmpl,
        "noplaylist": True,
        "socket_timeout": 25,
        "quiet": False,
        **_auth_options(),
    }
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
            path = ydl.prepare_filename(info)
    except Exception as exc:
        raise DownloadError(str(exc)) from exc

    if not os.path.exists(path):
        alt = os.path.splitext(path)[0] + ".mp4"
        if os.path.exists(alt):
            path = alt
    if not os.path.exists(path):
        raise DownloadError(f"Downloaded file not found: {path}")
    return path, info, sha256_file(path)
