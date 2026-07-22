"""
Ken Burns Slideshow Generator
==============================
Tạo video slideshow từ nhiều ảnh với hiệu ứng Ken Burns (pan + zoom).

Layout mỗi slide:
- Layer dưới: ảnh scale FILL toàn frame + blur mạnh (nền mờ)
- Layer trên: ảnh giữ nguyên tỷ lệ (aspect ratio), fit vào giữa frame

Mỗi ảnh sẽ có 1 trong các hiệu ứng ngẫu nhiên:
- Zoom in chậm (từ 1.0x → 1.2x)
- Zoom out chậm (từ 1.2x → 1.0x)
- Pan lên (di chuyển từ dưới lên)
- Pan xuống (di chuyển từ trên xuống)
- Pan trái → phải
- Pan phải → trái
- Kết hợp zoom + pan

Giữa các ảnh có hiệu ứng xfade (crossfade mượt).
"""

import os
import random
import subprocess
import tempfile
from pathlib import Path
from typing import List, Tuple

from vtool.core.ffmpeg import IMAGE_EXTENSIONS, list_media_files
from vtool.replace_bg_textmask.config import TextMaskConfig


# Các kiểu hiệu ứng Ken Burns
EFFECTS = [
    "zoom_in",
    "zoom_out",
    "pan_up",
    "pan_down",
    "pan_left",
    "pan_right",
    "zoom_in_pan_up",
    "zoom_in_pan_down",
    "zoom_out_pan_left",
    "zoom_out_pan_right",
]


def _get_zoom_expr(effect: str, zoom_min: float, zoom_max: float, total_frames: int) -> str:
    """Trả về zoom expression dựa trên effect type."""
    z_range = zoom_max - zoom_min

    if "zoom_in" in effect:
        return f"{zoom_min}+{z_range}*(on/{total_frames})"
    elif "zoom_out" in effect:
        return f"{zoom_max}-{z_range}*(on/{total_frames})"
    else:
        return f"{(zoom_min + zoom_max) / 2}"


def _get_pan_exprs(effect: str, total_frames: int) -> Tuple[str, str]:
    """Trả về (x_expr, y_expr) cho zoompan dựa trên effect type."""
    if "pan_left" in effect:
        x_expr = f"(iw-iw/zoom)*(1-on/{total_frames})"
        y_expr = "(ih-ih/zoom)/2"
    elif "pan_right" in effect:
        x_expr = f"(iw-iw/zoom)*(on/{total_frames})"
        y_expr = "(ih-ih/zoom)/2"
    elif "pan_up" in effect:
        x_expr = "(iw-iw/zoom)/2"
        y_expr = f"(ih-ih/zoom)*(1-on/{total_frames})"
    elif "pan_down" in effect:
        x_expr = "(iw-iw/zoom)/2"
        y_expr = f"(ih-ih/zoom)*(on/{total_frames})"
    else:
        x_expr = "(iw-iw/zoom)/2"
        y_expr = "(ih-ih/zoom)/2"

    return x_expr, y_expr


def _build_segment_filter(
    width: int,
    height: int,
    duration: float,
    fps: int,
    zoom_min: float,
    zoom_max: float,
    effect: str,
    blur_strength: int = 40,
) -> str:
    """
    Build filter cho 1 slide: blur background + ảnh giữ tỷ lệ ở giữa + Ken Burns.

    Cách làm:
    1. split input thành 2 streams
    2. Stream 1 (blur bg): scale fill full frame → blur mạnh → zoompan
    3. Stream 2 (main): scale fit (giữ tỷ lệ, pad transparent) → zoompan
    4. Overlay main lên blur bg

    Vì zoompan chỉ nhận 1 input image, ta dùng approach khác:
    - Composite ảnh trước (blur bg + main overlay) thành 1 frame
    - Rồi apply zoompan lên frame composite đó
    """
    total_frames = int(duration * fps)

    zoom_expr = _get_zoom_expr(effect, zoom_min, zoom_max, total_frames)
    x_expr, y_expr = _get_pan_exprs(effect, total_frames)

    # Filter chain:
    # [0:v] → split thành [bg] và [fg]
    # [bg] → scale fill + blur → [blurred]
    # [fg] → scale fit (giữ tỷ lệ) + pad transparent → [fitted]
    # [blurred][fitted] → overlay center → [composed]
    # [composed] → scale lên 2x (headroom cho zoompan) → zoompan → output
    
    # Scale factor cho zoompan headroom (cần lớn hơn output để zoom không bị cắt)
    scale_factor = 2

    filter_str = (
        # Split input
        f"split[bg][fg];"
        # Blur background: scale FILL (crop thừa) + blur
        f"[bg]scale={width * scale_factor}:{height * scale_factor}:"
        f"force_original_aspect_ratio=increase,"
        f"crop={width * scale_factor}:{height * scale_factor},"
        f"gblur=sigma={blur_strength}[blurred];"
        # Main image: scale FIT (giữ tỷ lệ, thêm transparent padding)
        f"[fg]scale={width * scale_factor}:{height * scale_factor}:"
        f"force_original_aspect_ratio=decrease,"
        f"pad={width * scale_factor}:{height * scale_factor}:"
        f"(ow-iw)/2:(oh-ih)/2:color=black@0.0,"
        f"format=rgba[fitted];"
        # Overlay main lên blur bg
        f"[blurred][fitted]overlay=0:0:format=auto[composed];"
        # Apply Ken Burns (zoompan) lên composite
        f"[composed]zoompan="
        f"z='{zoom_expr}':"
        f"x='{x_expr}':"
        f"y='{y_expr}':"
        f"d={total_frames}:"
        f"s={width}x{height}:"
        f"fps={fps},"
        f"setsar=1"
    )

    return filter_str


def generate_slideshow_video(
    images: List[str],
    output_path: str,
    width: int,
    height: int,
    total_duration: float,
    config: TextMaskConfig,
) -> str:
    """
    Tạo video slideshow từ danh sách ảnh với hiệu ứng Ken Burns + crossfade.
    Mỗi ảnh có blur background + giữ nguyên tỷ lệ ở giữa.

    Returns: path tới video slideshow tạm
    """
    slide_duration = config.slide_duration
    transition = config.slide_transition
    fps = config.slide_fps
    zoom_min, zoom_max = config.slide_zoom_range

    # Tính số slide cần dùng
    effective_per_slide = slide_duration - transition
    if effective_per_slide <= 0:
        effective_per_slide = slide_duration * 0.7

    num_slides = max(2, int(total_duration / effective_per_slide) + 1)

    # Lặp lại ảnh nếu không đủ
    if config.slide_random_order:
        random.shuffle(images)

    slide_images = []
    while len(slide_images) < num_slides:
        batch = images.copy()
        if config.slide_random_order:
            random.shuffle(batch)
        slide_images.extend(batch)
    slide_images = slide_images[:num_slides]

    # Random effect cho mỗi slide
    effects = [random.choice(EFFECTS) for _ in range(num_slides)]

    # Approach: tạo từng segment video (blur bg + fit image + zoompan) rồi xfade concat
    # Lý do: filter_complex với nhiều inputs + zoompan phức tạp dễ lỗi
    return _generate_slideshow_segments(
        slide_images, output_path, width, height,
        total_duration, slide_duration, transition, fps,
        zoom_min, zoom_max, effects, config,
    )


def _generate_slideshow_segments(
    images: List[str],
    output_path: str,
    width: int,
    height: int,
    total_duration: float,
    slide_duration: float,
    transition: float,
    fps: int,
    zoom_min: float,
    zoom_max: float,
    effects: List[str],
    config: TextMaskConfig,
) -> str:
    """
    Tạo slideshow bằng cách: render từng slide → xfade concat.
    Mỗi slide = blur background + ảnh fit giữa + Ken Burns effect.
    """
    temp_dir = tempfile.mkdtemp(prefix="slideshow_")
    segment_paths = []

    # Blur strength cho background
    blur_strength = getattr(config, 'slide_blur_strength', 40)

    # Tạo từng segment video cho mỗi ảnh
    for i, (img_path, effect) in enumerate(zip(images, effects)):
        seg_output = os.path.join(temp_dir, f"seg_{i:04d}.mp4")

        filter_str = _build_segment_filter(
            width=width,
            height=height,
            duration=slide_duration,
            fps=fps,
            zoom_min=zoom_min,
            zoom_max=zoom_max,
            effect=effect,
            blur_strength=blur_strength,
        )

        cmd = [
            "ffmpeg", "-y",
            "-loop", "1", "-t", str(slide_duration),
            "-i", img_path,
            "-filter_complex", filter_str,
            "-c:v", "libx264", "-preset", "fast", "-crf", "18",
            "-pix_fmt", "yuv420p",
            "-t", str(slide_duration),
            seg_output,
        ]

        proc = subprocess.run(
            cmd, capture_output=True, text=True,
            timeout=600, encoding="utf-8", errors="replace"
        )

        if proc.returncode == 0:
            segment_paths.append(seg_output)
        else:
            # Fallback: nếu filter phức tạp lỗi, thử filter đơn giản hơn (không blur bg)
            seg_output_fb = _render_segment_simple(
                img_path, seg_output, width, height,
                slide_duration, fps, zoom_min, zoom_max, effect
            )
            if seg_output_fb:
                segment_paths.append(seg_output_fb)

    if not segment_paths:
        raise RuntimeError("Failed to generate any slideshow segments")

    # Tạo output path
    if not output_path:
        output_path = os.path.join(
            tempfile.gettempdir(),
            f"slideshow_{os.getpid()}_{random.randint(1000, 9999)}.mp4"
        )

    # Concat segments với xfade
    if len(segment_paths) == 1:
        # Chỉ 1 segment, loop nó
        cmd = [
            "ffmpeg", "-y",
            "-stream_loop", "-1",
            "-i", segment_paths[0],
            "-c:v", "libx264", "-preset", "fast", "-crf", "18",
            "-pix_fmt", "yuv420p",
            "-t", str(total_duration),
            output_path,
        ]
        subprocess.run(cmd, capture_output=True, text=True, timeout=3600,
                       encoding="utf-8", errors="replace")
        _cleanup_segments(temp_dir)
        return output_path

    # Dùng xfade chain cho segments
    filter_parts = []
    input_args = []

    for i, seg in enumerate(segment_paths):
        input_args.extend(["-i", seg])

    # Build xfade chain
    num = len(segment_paths)
    current_offset = slide_duration - transition

    if num == 2:
        filter_parts.append(
            f"[0:v][1:v]xfade=transition=fade:"
            f"duration={transition}:offset={current_offset}[outv]"
        )
    else:
        filter_parts.append(
            f"[0:v][1:v]xfade=transition=fade:"
            f"duration={transition}:offset={current_offset}[xf0]"
        )
        for i in range(2, num):
            current_offset += (slide_duration - transition)
            prev = f"[xf{i - 2}]"
            next_v = f"[{i}:v]"
            out = f"[xf{i - 1}]" if i < num - 1 else "[outv]"
            filter_parts.append(
                f"{prev}{next_v}xfade=transition=fade:"
                f"duration={transition}:offset={current_offset}{out}"
            )

    filter_complex = ";".join(filter_parts)

    cmd = [
        "ffmpeg", "-y",
        *input_args,
        "-filter_complex", filter_complex,
        "-map", "[outv]",
        "-c:v", "libx264", "-preset", "fast", "-crf", "18",
        "-pix_fmt", "yuv420p",
        "-t", str(total_duration),
        output_path,
    ]

    proc = subprocess.run(
        cmd, capture_output=True, text=True,
        timeout=3600, encoding="utf-8", errors="replace"
    )

    if proc.returncode != 0:
        # Final fallback: concat demuxer (không có fade transition nhưng chắc chắn hoạt động)
        _concat_fallback(segment_paths, output_path, total_duration, temp_dir)
    else:
        _cleanup_segments(temp_dir)

    return output_path


def _render_segment_simple(
    img_path: str,
    output_path: str,
    width: int,
    height: int,
    duration: float,
    fps: int,
    zoom_min: float,
    zoom_max: float,
    effect: str,
) -> str:
    """
    Fallback render 1 segment: chỉ zoompan đơn giản (scale fill + zoom), không blur overlay.
    Dùng khi filter phức tạp (blur + overlay) bị lỗi.
    """
    total_frames = int(duration * fps)

    zoom_expr = _get_zoom_expr(effect, zoom_min, zoom_max, total_frames)
    x_expr, y_expr = _get_pan_exprs(effect, total_frames)

    filter_str = (
        f"scale={width * 2}:{height * 2},"
        f"zoompan=z='{zoom_expr}':"
        f"x='{x_expr}':"
        f"y='{y_expr}':"
        f"d={total_frames}:"
        f"s={width}x{height}:"
        f"fps={fps},"
        f"setsar=1"
    )

    cmd = [
        "ffmpeg", "-y",
        "-loop", "1", "-t", str(duration),
        "-i", img_path,
        "-vf", filter_str,
        "-c:v", "libx264", "-preset", "fast", "-crf", "18",
        "-pix_fmt", "yuv420p",
        "-t", str(duration),
        output_path,
    ]

    proc = subprocess.run(
        cmd, capture_output=True, text=True,
        timeout=600, encoding="utf-8", errors="replace"
    )

    if proc.returncode == 0:
        return output_path
    return None


def _concat_fallback(segments: List[str], output_path: str, duration: float, temp_dir: str):
    """Concat đơn giản bằng concat demuxer khi xfade lỗi."""
    concat_file = os.path.join(temp_dir, "concat.txt")
    with open(concat_file, "w") as f:
        for seg in segments:
            f.write(f"file '{seg}'\n")

    cmd = [
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0",
        "-i", concat_file,
        "-c:v", "libx264", "-preset", "fast", "-crf", "18",
        "-pix_fmt", "yuv420p",
        "-t", str(duration),
        output_path,
    ]

    subprocess.run(
        cmd, capture_output=True, text=True,
        timeout=3600, encoding="utf-8", errors="replace"
    )

    _cleanup_segments(temp_dir)


def _cleanup_segments(temp_dir: str):
    """Xoá temp segments."""
    import shutil
    try:
        shutil.rmtree(temp_dir, ignore_errors=True)
    except Exception:
        pass
