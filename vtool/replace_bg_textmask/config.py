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
    bar_ratio: float = 0.35    # Chiều cao dải đen = bao nhiêu % frame (0.35 = 35% phía dưới)

    # Slideshow settings (dùng nhiều ảnh nền với hiệu ứng Ken Burns)
    slideshow_mode: bool = True         # True = dùng nhiều ảnh slideshow, False = dùng 1 video/ảnh cũ
    slide_duration: float = 8.0         # Mỗi ảnh hiển thị bao nhiêu giây
    slide_transition: float = 1.5       # Thời gian chuyển cảnh giữa 2 ảnh (giây, fade)
    slide_zoom_range: tuple = (1.0, 1.2)  # Zoom từ min đến max (1.0 = gốc, 1.2 = zoom 20%)
    slide_pan_speed: float = 0.03       # Tốc độ pan (% frame/giây) - di chuyển chậm
    slide_fps: int = 30                 # FPS cho slideshow output
    slide_random_order: bool = True     # Xáo trộn thứ tự ảnh
    slide_blur_strength: int = 40       # Độ mờ nền blur phía sau ảnh (sigma, cao = mờ hơn)

    # Options
    limit: int = None
    resolution: int = None
