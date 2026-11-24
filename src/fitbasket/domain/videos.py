"""How-to videos for exercises and recipes.

With YOUTUBE_API_KEY set this calls the YouTube Data API v3. Without it, it returns a
YouTube search link rather than inventing video IDs.
"""

from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request

from ..models import Video

API_URL = "https://www.googleapis.com/youtube/v3/search"


def search_link(query: str) -> Video:
    url = "https://www.youtube.com/results?" + urllib.parse.urlencode({"search_query": query})
    return Video(title=f"YouTube search: {query}", url=url, source="search_link")


def find_videos(query: str, max_results: int = 3, api_key: str | None = None, timeout: float = 5.0) -> list[Video]:
    query = query.strip()[:120]
    if not query:
        raise ValueError("query must not be empty")
    api_key = api_key or os.getenv("YOUTUBE_API_KEY")
    if not api_key:
        return [search_link(query)]

    params = urllib.parse.urlencode(
        {
            "part": "snippet",
            "q": query,
            "type": "video",
            "maxResults": max(1, min(max_results, 5)),
            "safeSearch": "strict",
            "relevanceLanguage": "en",
            "key": api_key,
        }
    )
    try:
        with urllib.request.urlopen(f"{API_URL}?{params}", timeout=timeout) as resp:  # noqa: S310
            items = json.load(resp).get("items", [])
    except Exception:
        # Degrade gracefully: a broken video lookup should never break the plan.
        return [search_link(query)]
    videos = [
        Video(
            title=it["snippet"]["title"],
            url=f"https://www.youtube.com/watch?v={it['id']['videoId']}",
            channel=it["snippet"].get("channelTitle"),
            source="youtube_api",
        )
        for it in items
        if it.get("id", {}).get("videoId")
    ]
    return videos or [search_link(query)]
