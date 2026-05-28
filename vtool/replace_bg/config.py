"""Configuration for replace_bg module."""

from dataclasses import dataclass, field


@dataclass
class ReplaceBgConfig:
    input_dir: str = "input_videos"
    background_dir: str = "backgrounds"
    output_dir: str = "output_videos"
    max_workers: int = 4
    output_format: str = "mp4"
    video_codec: str = "libx264"
    audio_codec: str = "aac"
    preset: str = "fast"
    crf: int = 23
    use_gpu: bool = False

    # Text detection
    auto_detect: bool = True  # Auto-detect text region
    text_ratio: float = 0.30  # Fallback nếu auto-detect thất bại
    detect_sample_times: list = field(default_factory=lambda: [1.0, 3.0, 5.0])
    limit: int = None  # Giới hạn số video xử lý
    resolution: int = None  # Output resolution (720, 1080, None=giữ nguyên)
