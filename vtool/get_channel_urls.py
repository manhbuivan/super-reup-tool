"""
Lấy danh sách video URLs từ YouTube channel.
Không dùng yt-dlp, dùng YouTube page scraping.
"""

import re
import sys
import requests


def get_channel_video_urls(channel_url: str, limit: int = None) -> list:
    """
    Lấy video URLs từ channel YouTube bằng scraping.
    
    Args:
        channel_url: URL channel (vd: https://youtube.com/@ChannelName)
        limit: Giới hạn số video
    
    Returns:
        List URLs
    """
    # Đảm bảo URL trỏ tới /videos
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

    # Tìm tất cả video IDs trong page source
    video_ids = re.findall(r'"videoId":"([a-zA-Z0-9_-]{11})"', resp.text)

    # Loại bỏ trùng lặp, giữ thứ tự
    seen = set()
    unique_ids = []
    for vid in video_ids:
        if vid not in seen:
            seen.add(vid)
            unique_ids.append(vid)

    if limit:
        unique_ids = unique_ids[:limit]

    urls = [f"https://www.youtube.com/watch?v={vid}" for vid in unique_ids]
    return urls


def save_urls(urls: list, output_file: str = "urls.txt"):
    """Lưu URLs ra file."""
    with open(output_file, "w", encoding="utf-8") as f:
        for url in urls:
            f.write(url + "\n")
