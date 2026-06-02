"""
Lấy danh sách video URLs từ YouTube channel.
Dùng scrapetube (lấy được TẤT CẢ video, không giới hạn 30).
Fallback: scraping HTML (chỉ lấy được ~30).
"""

import re
import sys
import requests


def get_channel_video_urls(channel_url: str, limit: int = None) -> list:
    """
    Lấy tất cả video URLs từ channel YouTube.
    """
    # Thử dùng scrapetube trước (lấy được tất cả)
    try:
        import scrapetube
        
        videos = scrapetube.get_channel(channel_url=channel_url, limit=limit)
        urls = []
        for video in videos:
            video_id = video.get("videoId", "")
            if video_id:
                urls.append(f"https://www.youtube.com/watch?v={video_id}")
        
        if urls:
            return urls
        # Nếu scrapetube trả rỗng → dùng fallback
    except ImportError:
        pass
    except Exception:
        pass

    # Fallback: scraping HTML (chỉ ~30 video)
    return _scrape_html_fallback(channel_url, limit)


def _scrape_html_fallback(channel_url: str, limit: int = None) -> list:
    """Fallback: lấy video IDs từ HTML (chỉ ~30)."""
    if "/videos" not in channel_url:
        channel_url = channel_url.rstrip("/") + "/videos"

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9",
    }

    try:
        resp = requests.get(channel_url, headers=headers, timeout=30)
        resp.raise_for_status()
    except Exception as e:
        print(f"❌ Không truy cập được channel: {e}")
        return []

    video_ids = re.findall(r'"videoId":"([a-zA-Z0-9_-]{11})"', resp.text)

    seen = set()
    unique_ids = []
    for vid in video_ids:
        if vid not in seen:
            seen.add(vid)
            unique_ids.append(vid)

    if limit:
        unique_ids = unique_ids[:limit]

    return [f"https://www.youtube.com/watch?v={vid}" for vid in unique_ids]


def save_urls(urls: list, output_file: str = "urls.txt"):
    """Lưu URLs ra file."""
    with open(output_file, "w", encoding="utf-8") as f:
        for url in urls:
            f.write(url + "\n")
