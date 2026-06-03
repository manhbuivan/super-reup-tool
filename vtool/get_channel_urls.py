"""
Lấy danh sách video URLs từ YouTube channel.
Dùng scrapetube (lấy được TẤT CẢ video, không giới hạn 30).
Fallback: scraping HTML (chỉ lấy được ~30).
"""

import re
import subprocess
import sys
import requests


def _ytdlp_get_urls(channel_url: str, limit: int = None) -> list:
    """Dùng yt-dlp để lấy tất cả video URL từ channel."""
    try:
        # Đảm bảo URL trỏ tới tab videos
        url = channel_url.rstrip("/")
        if "/videos" not in url:
            url += "/videos"

        cmd = [
            "yt-dlp",
            "--flat-playlist",
            "--print", "url",
            url
        ]
        if limit:
            cmd.extend(["--playlist-end", str(limit)])

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)

        if result.returncode == 0 and result.stdout.strip():
            urls = [line.strip() for line in result.stdout.strip().split("\n") if line.strip()]
            if len(urls) > 30:  # yt-dlp lấy được nhiều hơn fallback
                return urls
            # Nếu yt-dlp cũng chỉ 30, vẫn trả (sẽ thử scrapetube sau)
            return urls
    except Exception:
        pass
    return []


def get_channel_video_urls(channel_url: str, limit: int = None) -> list:
    """
    Lấy tất cả video URLs từ channel YouTube.
    Ưu tiên yt-dlp (lấy được tất cả video).
    Fallback: scrapetube → scraping HTML.
    """
    # Thử yt-dlp trước (đáng tin cậy nhất, lấy được tất cả)
    urls = _ytdlp_get_urls(channel_url, limit)
    if urls:
        return urls

    # Thử scrapetube
    try:
        import scrapetube

        try:
            videos = scrapetube.get_channel(channel_url=channel_url, limit=limit)
            urls = []
            for video in videos:
                video_id = video.get("videoId", "")
                if video_id:
                    urls.append(f"https://www.youtube.com/watch?v={video_id}")
            if urls:
                return urls
        except Exception:
            pass

        # Resolve channel ID rồi thử lại
        channel_id = _resolve_channel_id(channel_url)
        if channel_id:
            videos = scrapetube.get_channel(channel_id=channel_id, limit=limit)
            urls = []
            for video in videos:
                video_id = video.get("videoId", "")
                if video_id:
                    urls.append(f"https://www.youtube.com/watch?v={video_id}")
            if urls:
                return urls

    except ImportError:
        pass
    except Exception:
        pass

    # Fallback: scraping HTML (chỉ ~30 video)
    return _scrape_html_fallback(channel_url, limit)


def _resolve_channel_id(channel_url: str) -> str:
    """Lấy channel ID từ URL channel (hỗ trợ @handle)."""
    try:
        url = channel_url.rstrip("/")
        if "/videos" not in url:
            url += "/videos"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept-Language": "en-US,en;q=0.9",
        }
        resp = requests.get(url, headers=headers, timeout=30)
        # Tìm channel ID trong HTML
        match = re.search(r'"channelId":"(UC[a-zA-Z0-9_-]{22})"', resp.text)
        if match:
            return match.group(1)
        # Tìm dạng khác
        match = re.search(r'channel_id=([a-zA-Z0-9_-]{24})', resp.text)
        if match:
            return match.group(1)
    except Exception:
        pass
    return ""


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
