"""Configuration for replace_bg_textmask module."""

from dataclasses import dataclass, field


@dataclass
class TextMaskConfig:
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

    # Text mask settings (dùng lumakey)
    threshold: int = 200       # Ngưỡng brightness để coi là text trắng (0-255, cao = chỉ giữ pixel rất sáng)
    softness: int = 10         # Độ mượt viền text (pixel feather), giúp text không bị răng cưa
    expand: int = 0            # Mở rộng mask (dilate) để giữ viền text đầy đủ hơn (0=tắt, tránh lỗi filter)
    text_region: str = "full"  # Vùng detect: "full" = toàn frame, "bottom" = chỉ nửa dưới
    text_ratio: float = 0.45   # Nếu text_region="bottom", giữ bao nhiêu % phía dưới
    shadow_remove: bool = True # Xoá shadow/outline đen quanh text (giữ sạch hơn)
    min_brightness: int = 180  # Brightness tối thiểu cho vùng soft (dưới threshold nhưng vẫn giữ 1 phần)

    # Dải nền đen mới (drawbox) để chữ nổi trên BG mới
    bar_opacity: float = 0.6   # Độ mờ dải đen phía dưới (0=không có, 0.6=mờ 60%, 1.0=đen hoàn toàn)
    bar_ratio: float = 0.25    # Chiều cao dải đen = bao nhiêu % frame (0.25 = 25% phía dưới)

    # Options
    limit: int = None
    resolution: int = None
