"""FFmpeg utilities - shared across modules."""

import json
import subprocess
from pathlib import Path


VIDEO_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv", ".webm", ".flv"}
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}


def get_video_info(video_path: str) -> dict:
    """Lấy thông tin video bằng ffprobe."""
    cmd = [
        "ffprobe", "-v", "quiet",
        "-print_format", "json",
        "-show_format", "-show_streams",
        video_path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if result.returncode != 0:
        raise RuntimeError(f"ffprobe failed for {video_path}: {result.stderr}")
    return json.loads(result.stdout)


def get_video_dimensions(video_path: str) -> tuple:
    """Trả về (width, height, duration, fps) của video."""
    info = get_video_info(video_path)
    for stream in info.get("streams", []):
        if stream.get("codec_type") == "video":
            w = int(stream["width"])
            h = int(stream["height"])
            duration = float(info["format"].get("duration", 0))
            r_frame_rate = stream.get("r_frame_rate", "30/1")
            num, den = map(int, r_frame_rate.split("/"))
            fps = num / den if den else 30
            return w, h, duration, fps
    raise RuntimeError(f"No video stream found in {video_path}")


def extract_frame(video_path: str, time_sec: float = 1.0) -> str:
    """Trích xuất 1 frame từ video tại thời điểm time_sec, trả về path ảnh tạm."""
    import tempfile
    output_path = tempfile.mktemp(suffix=".png")
    cmd = [
        "ffmpeg", "-y", "-ss", str(time_sec),
        "-i", video_path,
        "-frames:v", "1",
        "-q:v", "2",
        output_path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if result.returncode != 0:
        raise RuntimeError(f"Failed to extract frame: {result.stderr}")
    return output_path


def list_media_files(directory: str, extensions: set = None) -> list:
    """Liệt kê media files trong thư mục."""
    if extensions is None:
        extensions = VIDEO_EXTENSIONS | IMAGE_EXTENSIONS
    files = []
    for f in sorted(Path(directory).iterdir()):
        if f.suffix.lower() in extensions:
            files.append(str(f))
    return files
