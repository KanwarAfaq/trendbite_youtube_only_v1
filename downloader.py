from __future__ import annotations

import hashlib
import os
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
    # GitHub Actions can restore a Netscape cookie file from the
    # YOUTUBE_COOKIES_B64 secret into YTDLP_COOKIE_FILE.
    if settings.ytdlp_cookie_file and os.path.exists(settings.ytdlp_cookie_file):
        return {"cookiefile": settings.ytdlp_cookie_file}

    # Useful for local runs only; hosted runners do not have the user's browser.
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

    # yt-dlp 2026+ uses an external JS runtime for YouTube challenges.
    # Deno is enabled by default by yt-dlp; the GitHub workflow installs it.
    # yt-dlp[default] also installs the matching yt-dlp-ejs package.
    opts = {
        "format": "bestvideo[height<=1080]+bestaudio/best[height<=1080]/best",
        "merge_output_format": "mp4",
        "outtmpl": outtmpl,
        "noplaylist": True,
        "socket_timeout": 30,
        "retries": 3,
        "fragment_retries": 3,
        "source_address": "0.0.0.0",  # Prefer IPv4 on hosted runners.
        "quiet": False,
        **_auth_options(),
    }

    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
            path = ydl.prepare_filename(info)
    except Exception as exc:
        message = str(exc)
        if "Sign in to confirm" in message or "not a bot" in message.lower():
            message += (
                " | YouTube challenged this runner. Configure the GitHub secret "
                "YOUTUBE_COOKIES_B64 (Netscape-format YouTube cookies encoded as base64) "
                "or use a self-hosted runner."
            )
        raise DownloadError(message) from exc

    if not os.path.exists(path):
        alt = os.path.splitext(path)[0] + ".mp4"
        if os.path.exists(alt):
            path = alt

    if not os.path.exists(path):
        raise DownloadError(f"Downloaded file not found: {path}")

    return path, info, sha256_file(path)
