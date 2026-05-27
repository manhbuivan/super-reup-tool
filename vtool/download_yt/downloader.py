"""
YouTube Downloader - Tải video + metadata + thumbnail.
Dùng yt-dlp.
"""

import json
import os
import subprocess
import sys
from pathlib import Path


def get_channel_urls(channel_url: str, limit: int = None, output_file: str = "urls.txt") -> list:
    """
    Lấy danh sách URL video từ channel/playlist YouTube.
    
    Args:
        channel_url: URL channel hoặc playlist
        limit: Giới hạn số video (None = lấy hết)
        output_file: File lưu danh sách URL
    
    Returns:
        List các URL
    """
    print(f"🔍 Đang lấy danh sách video từ: {channel_url}")
    
    cmd = [
        "yt-dlp",
        "--flat-playlist",
        "--print", "url",
        channel_url
    ]
    
    if limit:
        cmd.extend(["--playlist-end", str(limit)])
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    if result.returncode != 0:
        print(f"❌ Lỗi lấy URL: {result.stderr[:300]}")
        sys.exit(1)
    
    urls = [line.strip() for line in result.stdout.strip().split("\n") if line.strip()]
    
    # Lưu ra file
    with open(output_file, "w", encoding="utf-8") as f:
        for url in urls:
            f.write(url + "\n")
    
    print(f"✅ Lấy được {len(urls)} URL → lưu vào {output_file}")
    return urls


def download_videos(urls: list, output_dir: str = "input_videos", quality: str = "best") -> list:
    """
    Tải video + metadata + thumbnail từ danh sách URL.
    
    Mỗi video tạo 3 file:
        - {title}.mp4
        - {title}.json (title, description, tags, upload_date)
        - {title}.jpg (thumbnail)
    
    Args:
        urls: Danh sách URL video
        output_dir: Thư mục output
        quality: Chất lượng video (best, 1080, 720)
    
    Returns:
        List các dict kết quả
    """
    os.makedirs(output_dir, exist_ok=True)
    
    total = len(urls)
    results = []
    
    print("=" * 60)
    print("📥 DOWNLOAD YOUTUBE VIDEOS")
    print("=" * 60)
    print(f"📂 Output: {output_dir}/")
    print(f"🎬 Videos: {total}")
    print(f"📊 Quality: {quality}")
    print("=" * 60)
    
    for i, url in enumerate(urls, 1):
        print(f"\n  [{i}/{total}] Downloading: {url}")
        
        result = _download_single(url, output_dir, quality)
        results.append(result)
        
        if result["status"] == "success":
            print(f"           ✅ {result['title']}")
        else:
            print(f"           ❌ {result['error'][:100]}")
    
    # Summary
    success = sum(1 for r in results if r["status"] == "success")
    print("\n" + "=" * 60)
    print(f"📊 KẾT QUẢ: ✅ {success}/{total} thành công")
    print("=" * 60)
    
    return results


def _download_single(url: str, output_dir: str, quality: str) -> dict:
    """Tải 1 video + metadata + thumbnail."""
    
    result = {"url": url, "status": "success", "title": "", "error": None}
    
    try:
        # Bước 1: Lấy metadata trước
        meta_cmd = [
            "yt-dlp",
            "--dump-json",
            "--no-download",
            url
        ]
        meta_result = subprocess.run(meta_cmd, capture_output=True, text=True, timeout=60)
        
        if meta_result.returncode != 0:
            result["status"] = "error"
            result["error"] = meta_result.stderr[:200]
            return result
        
        meta = json.loads(meta_result.stdout)
        title = _sanitize_filename(meta.get("title", "untitled"))
        result["title"] = title
        
        # Lưu metadata json
        meta_info = {
            "title": meta.get("title", ""),
            "description": meta.get("description", ""),
            "tags": meta.get("tags", []),
            "upload_date": meta.get("upload_date", ""),
            "duration": meta.get("duration", 0),
            "channel": meta.get("channel", ""),
            "view_count": meta.get("view_count", 0),
            "original_url": url,
        }
        
        json_path = os.path.join(output_dir, f"{title}.json")
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(meta_info, f, ensure_ascii=False, indent=2)
        
        # Bước 2: Tải thumbnail
        thumb_url = meta.get("thumbnail", "")
        if thumb_url:
            thumb_path = os.path.join(output_dir, f"{title}.jpg")
            _download_thumbnail(thumb_url, thumb_path)
        
        # Bước 3: Tải video
        video_path = os.path.join(output_dir, f"{title}.mp4")
        
        # Skip nếu đã tải rồi
        if os.path.exists(video_path):
            print(f"           ⏭️  Đã tồn tại, skip")
            return result
        
        format_str = _get_format_string(quality)
        
        dl_cmd = [
            "yt-dlp",
            "-f", format_str,
            "--merge-output-format", "mp4",
            "-o", video_path,
            "--no-playlist",
            url
        ]
        
        dl_result = subprocess.run(dl_cmd, capture_output=True, text=True, timeout=1800)
        
        if dl_result.returncode != 0:
            result["status"] = "error"
            result["error"] = dl_result.stderr[:200]
            return result
        
    except Exception as e:
        result["status"] = "error"
        result["error"] = str(e)
    
    return result


def _download_thumbnail(url: str, output_path: str):
    """Tải thumbnail từ URL."""
    try:
        import requests
        resp = requests.get(url, timeout=15)
        if resp.status_code == 200:
            with open(output_path, "wb") as f:
                f.write(resp.content)
    except Exception:
        pass  # Thumbnail không quan trọng, skip nếu lỗi


def _sanitize_filename(name: str) -> str:
    """Loại bỏ ký tự không hợp lệ cho filename."""
    invalid_chars = '<>:"/\\|?*'
    for ch in invalid_chars:
        name = name.replace(ch, "")
    # Giới hạn độ dài
    name = name.strip()
    if len(name) > 150:
        name = name[:150]
    return name


def _get_format_string(quality: str) -> str:
    """Trả về format string cho yt-dlp. Ưu tiên h264 để tương thích Windows."""
    if quality == "720":
        return "bestvideo[height<=720][vcodec^=avc1]+bestaudio[acodec^=mp4a]/bestvideo[height<=720]+bestaudio/best[height<=720]"
    elif quality == "1080":
        return "bestvideo[height<=1080][vcodec^=avc1]+bestaudio[acodec^=mp4a]/bestvideo[height<=1080]+bestaudio/best[height<=1080]"
    else:
        return "bestvideo[vcodec^=avc1]+bestaudio[acodec^=mp4a]/bestvideo+bestaudio/best"
