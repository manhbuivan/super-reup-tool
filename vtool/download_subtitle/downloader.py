"""
Download subtitles from YouTube using youtube-transcript-api.
Không cần yt-dlp, cookies, hay PO Token.
"""

import os
import sys
import re


def extract_video_id(url: str) -> str:
    """Lấy video ID từ URL YouTube."""
    patterns = [
        r'(?:v=|/v/|youtu\.be/)([a-zA-Z0-9_-]{11})',
        r'(?:embed/)([a-zA-Z0-9_-]{11})',
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return url  # Assume it's already an ID


def download_single_subtitle(url: str, output_dir: str, languages: list = None) -> dict:
    """
    Tải subtitle 1 video, lưu thành file .srt.
    
    Returns:
        dict: {url, status, title, srt_path, error}
    """
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
        from youtube_transcript_api.formatters import SRTFormatter
    except ImportError:
        print("❌ Cần cài: pip install youtube-transcript-api")
        sys.exit(1)

    if languages is None:
        languages = ["ja", "en", "vi"]

    video_id = extract_video_id(url)
    result = {"url": url, "video_id": video_id, "status": "success", "srt_path": "", "error": None}

    try:
        # Lấy transcript
        ytt_api = YouTubeTranscriptApi()
        transcript = ytt_api.fetch(video_id, languages=languages)

        # Format thành SRT
        formatter = SRTFormatter()
        srt_content = formatter.format_transcript(transcript)

        # Lấy title từ video_id (dùng làm tên file)
        # Tạo tên file từ video_id
        srt_filename = f"{video_id}.srt"
        srt_path = os.path.join(output_dir, srt_filename)

        os.makedirs(output_dir, exist_ok=True)
        with open(srt_path, "w", encoding="utf-8") as f:
            f.write(srt_content)

        result["srt_path"] = srt_path

    except Exception as e:
        result["status"] = "error"
        result["error"] = str(e)

    return result


def download_subtitles(urls: list, output_dir: str = "input_videos", languages: list = None) -> list:
    """
    Tải subtitle hàng loạt.
    
    Args:
        urls: Danh sách URL video
        output_dir: Thư mục output
        languages: Danh sách ngôn ngữ ưu tiên (default: ja, en, vi)
    """
    if languages is None:
        languages = ["ja", "en", "vi"]

    total = len(urls)
    results = []

    print("=" * 60)
    print("📝 DOWNLOAD SUBTITLES")
    print("=" * 60)
    print(f"📂 Output: {output_dir}/")
    print(f"🎬 Videos: {total}")
    print(f"🌐 Languages: {', '.join(languages)}")
    print("=" * 60)

    for i, url in enumerate(urls, 1):
        result = download_single_subtitle(url, output_dir, languages)
        results.append(result)

        if result["status"] == "success":
            print(f"  [{i}/{total}] ✅ {result['video_id']}")
        else:
            print(f"  [{i}/{total}] ❌ {result['video_id']} - {result['error'][:80]}")

    success = sum(1 for r in results if r["status"] == "success")
    print("\n" + "=" * 60)
    print(f"📊 KẾT QUẢ: ✅ {success}/{total} thành công")
    print("=" * 60)

    return results
