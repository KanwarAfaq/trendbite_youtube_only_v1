from __future__ import annotations

import argparse
import json
import os
import time

from config import settings
from downloader import download_youtube
from facebook_publisher import FacebookPublisher
from supabase_store import SupabaseStore
from youtube_discovery import YouTubeDiscoveryError, build_live_queries, discover


def _caption(meta: dict) -> str:
    title = str(meta.get("title") or "").strip()
    author = str(meta.get("source_author") or "YouTube creator").strip()
    url = str(meta.get("source_url") or "").strip()
    license_name = str(meta.get("source_license") or "").strip()
    credit = f"Source: {title} — {author}"
    if license_name.lower() == "creativecommon":
        credit += " (Creative Commons)"
    return f"{title}\n\n{credit}\n{url}".strip()


def run(*, post: bool, count: int | None = None, delay: int | None = None) -> dict:
    target = max(0, int(settings.video_post_count if count is None else count))
    delay_seconds = max(0, int(settings.video_post_delay_seconds if delay is None else delay))
    max_attempts = max(1, int(settings.video_max_attempts))

    print("\n=== TrendBite LIVE YouTube -> Facebook bot ===")
    print("Source: YouTube only")
    print("Discovery: LIVE generated queries (no long static query list)")
    print("Themes:", " | ".join(settings.discovery_themes))
    print(f"YouTube API keys configured: {len(settings.youtube_api_keys)}")
    print(f"Target successful posts: {target}")
    print(f"Delay between successful posts: {delay_seconds}s")
    print(f"YouTube license filter: {settings.youtube_video_license}")
    if not post:
        print("DRY RUN: videos will be selected but not downloaded or posted")

    store = SupabaseStore()
    posted = 0
    considered = 0
    attempts = 0
    errors: list[str] = []
    query_history: list[str] = []

    while attempts < max_attempts and posted < target:
        attempts += 1
        print(f"\n=== Live discovery attempt {attempts}/{max_attempts} ===")
        attempt_queries = build_live_queries(attempts)
        query_history.extend(attempt_queries)
        try:
            candidates = discover(attempt=attempts, queries=attempt_queries)
        except YouTubeDiscoveryError as exc:
            print("Discovery failed:", exc)
            errors.append(str(exc))
            # A later attempt will not fix a total API-key failure.
            break

        if not candidates:
            print("No reusable candidates in this freshness window; widening on next attempt")
            continue

        new_this_attempt = 0
        for meta in candidates:
            if posted >= target:
                break
            considered += 1
            url = meta["source_url"]
            old = store.find_by_source_url(url) or store.find_by_source_identity("youtube", meta["source_content_id"])
            if old:
                print(f"history skip: {old.get('status')} {url}")
                continue

            new_this_attempt += 1
            title = str(meta.get("title") or "")
            print(
                f"candidate: published={meta.get('source_published_at')} "
                f"views={meta.get('view_count', 0)} title={title[:90]}"
            )

            if not post:
                posted += 1
                print("DRY RUN selected:", url)
                continue

            rights_status = "licensed" if str(meta.get("source_license") or "").lower() == "creativecommon" else "permission"
            content = store.create_candidate(meta, rights_status=rights_status)
            video_path = None
            try:
                video_path, _info, digest = download_youtube(url)
                if store.already_posted_hash(digest):
                    store.update_status(content["id"], "duplicate")
                    print("duplicate hash skip:", url)
                    continue
                store.save_download_metadata(content["id"], digest)

                caption = _caption(meta)
                facebook = FacebookPublisher()
                print("Facebook page:", facebook.validate_page_token())
                if settings.facebook_publish_mode == "reel":
                    result = facebook.publish_reel(video_path, caption, title)
                else:
                    result = facebook.publish_regular_video(video_path, caption, title)

                facebook_video_id = str(result.get("video_id") or result.get("id") or "") or None
                store.record_facebook_post(
                    content_id=content["id"],
                    facebook_video_id=facebook_video_id,
                    caption=caption,
                    status="posted",
                    raw_response=result,
                )
                store.update_status(content["id"], "posted")
                posted += 1
                print(f"Posted to Facebook ({posted}/{target}):", result)

                if posted < target and delay_seconds > 0:
                    print(f"Waiting {delay_seconds}s before next successful post")
                    time.sleep(delay_seconds)
            except Exception as exc:
                errors.append(str(exc))
                print("post/download skip:", exc)
                try:
                    store.update_status(content["id"], "failed", str(exc)[:1500])
                except Exception:
                    pass
            finally:
                if video_path and settings.delete_local_after_post and os.path.exists(video_path):
                    os.remove(video_path)
                    print("Deleted local video:", video_path)

        if posted < target:
            if new_this_attempt == 0:
                print("All returned candidates were already in history; changing live queries/freshness window")
            print(f"Attempt {attempts} complete; successful={posted}/{target}")

    summary = {
        "target": target,
        "posted": posted,
        "considered": considered,
        "attempts": attempts,
        "success": posted >= target,
        "shortfall": max(0, target - posted),
        "delay_seconds": delay_seconds,
        "api_keys_configured": len(settings.youtube_api_keys),
        "themes": list(settings.discovery_themes),
        "live_queries_used": query_history,
        "errors": errors[-10:],
    }
    print("\n=== FINAL SUMMARY ===")
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return summary


def main():
    parser = argparse.ArgumentParser(description="TrendBite live YouTube discovery + Facebook video poster")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--post", action="store_true", help="Publish selected videos to Facebook")
    mode.add_argument("--dry-run", action="store_true", help="Discover/select without downloading or Facebook posting")
    parser.add_argument("--count", type=int, help="Override VIDEO_POST_COUNT")
    parser.add_argument("--delay", type=int, help="Override VIDEO_POST_DELAY_SECONDS")
    args = parser.parse_args()
    summary = run(post=bool(args.post), count=args.count, delay=args.delay)

    # A scheduled posting run is only successful when it reaches its target.
    # This prevents GitHub Actions from showing green after posting 0/10.
    if args.post and not summary["success"]:
        print(
            f"ERROR: posting target not reached: "
            f"{summary['posted']}/{summary['target']} successful posts"
        )
        raise SystemExit(2)


if __name__ == "__main__":
    main()
