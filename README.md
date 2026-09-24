# TrendBite YouTube-only Video Bot

This build removes TikTok, Instagram, Facebook-source discovery, AI scoring, AI providers, social search, ranking, and article agents.

Pipeline:

YouTube Data API -> duplicate check -> download selected video -> Facebook -> delete local file

## Existing `.env`

Copy your existing `.env` into this folder. Your existing YouTube, Facebook, and Supabase values are reused.

Add/update the values from `ENV_YOUTUBE_ONLY.txt`.

The two main controls are:

```env
VIDEO_POST_COUNT=3
VIDEO_POST_DELAY_SECONDS=60
```

For 10 videos with 5 minutes between successful posts:

```env
VIDEO_POST_COUNT=10
VIDEO_POST_DELAY_SECONDS=300
```

## Install

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -U -r requirements.txt
```

## Verify

```powershell
python preflight.py
```

## Dry run

```powershell
python video_bot.py --dry-run
```

## Post

```powershell
python video_bot.py --post
```

Temporary command-line overrides:

```powershell
python video_bot.py --post --count 5 --delay 120
```

## About "no restriction"

There is no AI score, safety/category gate, source-platform crawling, or bot-side duration limit by default. Duplicate protection remains. The default YouTube search uses Creative Commons because standard YouTube licensing does not automatically grant permission to copy a video to Facebook. If you own or are licensed to repost specific standard-license videos, use your authorized channel IDs or adjust the license setting accordingly.
