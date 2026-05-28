"""Configuration for replace_bg_colorkey module."""

from dataclasses import dataclass, field


@dataclass
class ColorKeyConfig:
    input_dir: str = "input_videos"
    background_dir: str = "backgrounds"
    output_dir: str = "output_videos"
    max_workers: int = 2
    output_format: str = "mp4"
    video_codec: str = "libx264"
    audio_codec: str = "aac"
    preset: str = "fast"
    crf: int = 23
    use_gpu: bool = False

    # Color key settings
    color: str = "0x2C3E50"  # Màu nền cần xoá (hex RGB, không có #)
    similarity: float = 0.3  # Độ tương đồng màu (0.0-1.0, cao = xoá nhiều hơn)
    blend: float = 0.1       # Độ mượt viền (0.0-1.0)

    # Options
    limit: int = None
    resolution: int = None
