"""
Twitch Downloader - Tải VOD/clip + tự cắt thành từng đoạn 1 tiếng.
Dùng yt-dlp (hỗ trợ Twitch).
"""

import json
import os
import subprocess
import sys
import math
from pathlib import Path


def get_twitch_vods(channel_url: str, limit: int = None, output_file: str = "twitch_urls.txt") -> list:
    """
    Lấy danh sách VOD URL từ channel Twitch.
    
    Args:
        channel_url: URL channel Twitch (vd: https://twitch.tv/username/videos)
        limit: Giới hạn số VOD
        output_file: File lưu danh sách URL
    
    Returns:
        List các URL
    """
    print(f"🔍 Đang lấy danh sách VOD từ: {channel_url}")
    
    # Đảm bảo URL trỏ tới /videos
    if "/videos" not in channel_url:
        channel_url = channel_url.rstrip("/") + "/videos"
    
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
    
    print(f"✅ Lấy được {len(urls)} VOD → lưu vào {output_file}")
    return urls


def download_twitch_videos(
    urls: list,
    output_dir: str = "input_videos",
    quality: str = "best",
    split_hours: float = 1.0,
) -> list:
    """
    Tải video từ Twitch + tự cắt thành từng đoạn.
    
    Args:
        urls: Danh sách URL VOD/clip
        output_dir: Thư mục output
        quality: Chất lượng (best, 1080, 720)
        split_hours: Cắt mỗi đoạn bao nhiêu giờ (default: 1.0)
    
    Returns:
        List kết quả
    """
    os.makedirs(output_dir, exist_ok=True)
    
    total = len(urls)
    results = []
    split_seconds = int(split_hours * 3600)
    
    print("=" * 60)
    print("📥 DOWNLOAD TWITCH VIDEOS")
    print("=" * 60)
    print(f"📂 Output: {output_dir}/")
    print(f"🎬 Videos: {total}")
    print(f"✂️  Split: mỗi {split_hours}h")
    print(f"📊 Quality: {quality}")
    print("=" * 60)
    
    for i, url in enumerate(urls, 1):
        print(f"\n  [{i}/{total}] {url}")
        
        result = _download_and_split(url, output_dir, quality, split_seconds)
        results.append(result)
        
        if result["status"] == "success":
            print(f"           ✅ {result['title']} → {result['parts']} phần")
        else:
            print(f"           ❌ {result['error'][:100]}")
    
    # Summary
    success = sum(1 for r in results if r["status"] == "success")
    total_parts = sum(r.get("parts", 0) for r in results)
    print("\n" + "=" * 60)
    print(f"📊 KẾT QUẢ: ✅ {success}/{total} video, tổng {total_parts} phần")
    print("=" * 60)
    
    return results


def _download_and_split(url: str, output_dir: str, quality: str, split_seconds: int) -> dict:
    """Tải 1 video Twitch, cắt nếu dài hơn split_seconds."""
    
    result = {"url": url, "status": "success", "title": "", "parts": 0, "error": None}
    
    try:
        # Bước 1: Lấy metadata
        meta_cmd = ["yt-dlp", "--dump-json", "--no-download", url]
        meta_result = subprocess.run(meta_cmd, capture_output=True, text=True, timeout=60)
        
        if meta_result.returncode != 0:
            result["status"] = "error"
            result["error"] = meta_result.stderr[:200]
            return result
        
        meta = json.loads(meta_result.stdout)
        title = _sanitize_filename(meta.get("title", "untitled"))
        duration = meta.get("duration", 0)
        result["title"] = title
        
        # Bước 2: Tải video
        temp_path = os.path.join(output_dir, f"_temp_{title}.mp4")
        
        format_str = _get_format_string(quality)
        
        dl_cmd = [
            "yt-dlp",
            "-f", format_str,
            "--merge-output-format", "mp4",
            "-o", temp_path,
            url
        ]
        
        dl_result = subprocess.run(dl_cmd, capture_output=True, text=True, timeout=7200)
        
        if dl_result.returncode != 0:
            result["status"] = "error"
            result["error"] = dl_result.stderr[:200]
            return result
        
        # Bước 3: Cắt video nếu dài hơn split_seconds
        if duration > split_seconds:
            parts = _split_video(temp_path, output_dir, title, duration, split_seconds, meta, url)
            result["parts"] = parts
            # Xoá file tạm
            if os.path.exists(temp_path):
                os.remove(temp_path)
        else:
            # Video ngắn, giữ nguyên
            final_path = os.path.join(output_dir, f"{title}.mp4")
            os.rename(temp_path, final_path)
            result["parts"] = 1
            
            # Lưu metadata
            _save_metadata(output_dir, title, meta, url)
            
            # Tải thumbnail
            thumb_url = meta.get("thumbnail", "")
            if thumb_url:
                _download_thumbnail(thumb_url, os.path.join(output_dir, f"{title}.jpg"))
    
    except Exception as e:
        result["status"] = "error"
        result["error"] = str(e)
        # Cleanup temp file
        temp_path = os.path.join(output_dir, f"_temp_{result.get('title', 'unknown')}.mp4")
        if os.path.exists(temp_path):
            os.remove(temp_path)
    
    return result


def _split_video(
    video_path: str, output_dir: str, title: str,
    duration: float, split_seconds: int, meta: dict, url: str
) -> int:
    """Cắt video thành nhiều phần, mỗi phần split_seconds giây."""
    
    num_parts = math.ceil(duration / split_seconds)
    
    for part in range(num_parts):
        start_time = part * split_seconds
        part_title = f"{title}_part{part + 1:02d}"
        part_path = os.path.join(output_dir, f"{part_title}.mp4")
        
        # Dùng FFmpeg cắt (không re-encode, rất nhanh)
        cmd = [
            "ffmpeg", "-y",
            "-ss", str(start_time),
            "-i", video_path,
            "-t", str(split_seconds),
            "-c", "copy",
            "-avoid_negative_ts", "make_zero",
            part_path
        ]
        
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        
        if proc.returncode != 0:
            continue
        
        # Lưu metadata cho mỗi phần
        part_meta = {
            "title": f"{meta.get('title', title)} - Part {part + 1}",
            "description": meta.get("description", ""),
            "tags": meta.get("tags", []),
            "duration": min(split_seconds, duration - start_time),
            "channel": meta.get("uploader", meta.get("channel", "")),
            "original_url": url,
            "part": part + 1,
            "total_parts": num_parts,
        }
        
        json_path = os.path.join(output_dir, f"{part_title}.json")
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(part_meta, f, ensure_ascii=False, indent=2)
        
        # Thumbnail (dùng chung cho tất cả parts)
        thumb_url = meta.get("thumbnail", "")
        if thumb_url:
            thumb_path = os.path.join(output_dir, f"{part_title}.jpg")
            _download_thumbnail(thumb_url, thumb_path)
    
    return num_parts


def _save_metadata(output_dir: str, title: str, meta: dict, url: str):
    """Lưu metadata ra file JSON."""
    meta_info = {
        "title": meta.get("title", title),
        "description": meta.get("description", ""),
        "tags": meta.get("tags", []),
        "duration": meta.get("duration", 0),
        "channel": meta.get("uploader", meta.get("channel", "")),
        "view_count": meta.get("view_count", 0),
        "original_url": url,
    }
    
    json_path = os.path.join(output_dir, f"{title}.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(meta_info, f, ensure_ascii=False, indent=2)


def _download_thumbnail(url: str, output_path: str):
    """Tải thumbnail."""
    try:
        import requests
        resp = requests.get(url, timeout=15)
        if resp.status_code == 200:
            with open(output_path, "wb") as f:
                f.write(resp.content)
    except Exception:
        pass


def _sanitize_filename(name: str) -> str:
    """Loại bỏ ký tự không hợp lệ cho filename."""
    invalid_chars = '<>:"/\\|?*'
    for ch in invalid_chars:
        name = name.replace(ch, "")
    name = name.strip()
    if len(name) > 150:
        name = name[:150]
    return name


def _get_format_string(quality: str) -> str:
    """Format string cho yt-dlp."""
    if quality == "720":
        return "bestvideo[height<=720]+bestaudio/best[height<=720]"
    elif quality == "1080":
        return "bestvideo[height<=1080]+bestaudio/best[height<=1080]"
    else:
        return "bestvideo+bestaudio/best"
