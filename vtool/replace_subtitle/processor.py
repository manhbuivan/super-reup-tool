"""
Replace Subtitle processor.
Tạo video mới: background + subtitle text render từ file .srt.
"""

import os
import sys
import random
import subprocess
import time
import glob
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor, as_completed

from vtool.core.ffmpeg import (
    VIDEO_EXTENSIONS, IMAGE_EXTENSIONS,
    get_video_dimensions, list_media_files
)


def _find_srt(input_dir: str, video_name: str) -> str:
    """Tìm file .srt tương ứng với video."""
    stem = Path(video_name).stem
    # Tìm tất cả .srt trong folder
    all_srt = glob.glob(os.path.join(input_dir, "*.srt"))
    
    # Tìm file có tên bắt đầu giống stem
    for srt in all_srt:
        srt_name = Path(srt).stem
        # So sánh: stem video có chứa trong tên srt hoặc ngược lại
        if stem in srt_name or srt_name.replace(".ja", "").replace(".en", "").replace(".vi", "") == stem:
            return srt
    
    # Nếu chỉ có 1 file srt và 1 video → match luôn
    if len(all_srt) == 1:
        return all_srt[0]
    
    return ""


def _get_subtitle_style(style: str, width: int, height: int) -> str:
    """Trả về subtitle style string cho FFmpeg."""
    if style == "banner":
        # Kiểu 2: nền đen full width, text to, sát mép dưới
        # FontSize tự scale theo chiều cao video (~5% height)
        font_size = max(24, int(height * 0.05))
        return (
            f"FontSize={font_size},FontName=Arial,PrimaryColour=&H00FFFFFF,"
            "OutlineColour=&H00000000,Outline=0,Shadow=0,"
            "BackColour=&HFF000000,BorderStyle=4,"
            f"MarginV=0,MarginL=10,MarginR=10,WrapStyle=2"
        )
    else:
        # Kiểu 1 (default): text trắng viền đen, nền mờ nhỏ
        return (
            "FontSize=28,FontName=Arial,PrimaryColour=&H00FFFFFF,"
            "OutlineColour=&H00000000,Outline=2,Shadow=1,"
            "BackColour=&H80000000,BorderStyle=4,MarginV=10"
        )


def process_single_subtitle(args: tuple) -> dict:
    """
    Tạo 1 video: background + subtitle từ .srt.
    FFmpeg: scale background + drawtext/subtitles filter.
    """
    video_path, background_path, srt_path, output_path, config = args

    start_time_proc = time.time()
    result = {
        "input": video_path,
        "output": output_path,
        "status": "success",
        "error": None,
    }

    try:
        # Lấy thông tin video gốc (để biết duration và audio)
        width, height, duration, fps = get_video_dimensions(video_path)

        # Xác định background type
        bg_ext = Path(background_path).suffix.lower()
        is_video_bg = bg_ext in VIDEO_EXTENSIONS

        # Codec
        if config.get("use_gpu"):
            vcodec = "h264_nvenc"
            extra_params = ["-preset", "p4", "-cq", str(config.get("crf", 23))]
        else:
            vcodec = "libx264"
            extra_params = ["-preset", config.get("preset", "fast"), "-crf", str(config.get("crf", 23))]

        # Escape srt path cho FFmpeg (Windows cần escape backslash và colon)
        srt_escaped = srt_path.replace("\\", "/").replace(":", "\\\\:")

        # Subtitle style
        sub_style = config.get("sub_style", "default")
        subtitle_style = _get_subtitle_style(sub_style, width, height)

        filter_complex = (
            f"[1:v]scale={width}:{height}:force_original_aspect_ratio=increase,"
            f"crop={width}:{height}[bg];"
            f"[bg]subtitles='{srt_escaped}':force_style='{subtitle_style}'[out]"
        )

        # Resolution scale
        if config.get("resolution"):
            target_h = config["resolution"]
            target_w = int(width * target_h / height)
            target_w = target_w if target_w % 2 == 0 else target_w + 1
            filter_complex = (
                f"[1:v]scale={width}:{height}:force_original_aspect_ratio=increase,"
                f"crop={width}:{height}[bg];"
                f"[bg]subtitles='{srt_escaped}':force_style='{subtitle_style}'[sub];"
                f"[sub]scale={target_w}:{target_h}[out]"
            )

        # Build command
        if is_video_bg:
            input_bg_args = ["-stream_loop", "-1", "-i", background_path]
        else:
            input_bg_args = ["-loop", "1", "-i", background_path]

        os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else ".", exist_ok=True)

        cmd = [
            "ffmpeg", "-y",
            "-i", video_path,
            *input_bg_args,
            "-filter_complex", filter_complex,
            "-map", "[out]", "-map", "0:a?",
            "-c:v", vcodec,
            *extra_params,
            "-c:a", "aac",
            "-b:a", "128k",
            "-t", str(duration),
            "-shortest",
            output_path
        ]

        proc = subprocess.run(
            cmd, capture_output=True, text=True,
            timeout=3600, encoding="utf-8", errors="replace"
        )

        if proc.returncode != 0:
            result["status"] = "error"
            stderr_lines = proc.stderr.split("\n")
            error_lines = [l for l in stderr_lines if any(
                k in l.lower() for k in ["error", "invalid", "failed", "cannot", "not found"]
            )]
            if error_lines:
                result["error"] = "\n".join(error_lines[-5:])
            else:
                result["error"] = "\n".join(stderr_lines[-5:])

    except Exception as e:
        result["status"] = "error"
        result["error"] = str(e)

    result["time"] = round(time.time() - start_time_proc, 1)
    return result


def batch_process_subtitle(
    input_dir: str = "input_videos",
    background_dir: str = "backgrounds",
    output_dir: str = "output_videos",
    max_workers: int = 2,
    use_gpu: bool = False,
    crf: int = 23,
    preset: str = "fast",
    resolution: int = None,
    limit: int = None,
    sub_style: str = "default",
):
    """Xử lý hàng loạt: background + subtitle."""
    import shutil

    os.makedirs(output_dir, exist_ok=True)

    # Lấy video input
    input_videos = list_media_files(input_dir, VIDEO_EXTENSIONS)
    if not input_videos:
        print(f"❌ Không tìm thấy video nào trong '{input_dir}/'")
        sys.exit(1)

    if limit:
        input_videos = input_videos[:limit]

    # Lấy backgrounds
    backgrounds = list_media_files(background_dir, VIDEO_EXTENSIONS | IMAGE_EXTENSIONS)
    if not backgrounds:
        print(f"❌ Không tìm thấy background nào trong '{background_dir}/'")
        sys.exit(1)

    # Header
    print("=" * 60)
    print("📝 REPLACE SUBTITLE - Background + Text Render")
    print("=" * 60)
    print(f"📂 Input videos:  {len(input_videos)} files")
    print(f"🖼️  Backgrounds:   {len(backgrounds)} files")
    print(f"⚙️  Workers:       {max_workers} parallel")
    print(f"🚀 GPU:           {'ON' if use_gpu else 'OFF'}")
    print("=" * 60)

    config = {
        "use_gpu": use_gpu,
        "crf": crf,
        "preset": preset,
        "resolution": resolution,
        "sub_style": sub_style,
    }

    # Chuẩn bị tasks
    tasks = []
    skipped = 0
    no_srt = 0

    for video_path in input_videos:
        stem = Path(video_path).stem
        output_name = f"{stem}.mp4"
        output_path = os.path.join(output_dir, output_name)

        if os.path.exists(output_path):
            skipped += 1
            continue

        # Tìm .srt
        srt_path = _find_srt(input_dir, Path(video_path).name)
        if not srt_path:
            no_srt += 1
            print(f"  ⚠️  Không có .srt: {stem}")
            continue

        bg = random.choice(backgrounds)
        tasks.append((video_path, bg, srt_path, output_path, config))

        # Copy metadata
        for ext in [".json", ".jpg"]:
            meta_src = os.path.join(input_dir, f"{stem}{ext}")
            if os.path.exists(meta_src):
                meta_dst = os.path.join(output_dir, f"{stem}{ext}")
                if not os.path.exists(meta_dst):
                    shutil.copy2(meta_src, meta_dst)

    if skipped > 0:
        print(f"⏭️  Bỏ qua {skipped} video đã có trong output")
    if no_srt > 0:
        print(f"⚠️  {no_srt} video không có file .srt")

    total = len(tasks)
    if total == 0:
        print("✅ Không có video nào cần xử lý")
        return

    success = 0
    errors = 0
    total_time_start = time.time()

    print(f"\n🚀 Bắt đầu xử lý {total} video...\n")

    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(process_single_subtitle, task): task for task in tasks}

        for i, future in enumerate(as_completed(futures), 1):
            result = future.result()
            status_icon = "✅" if result["status"] == "success" else "❌"
            filename = Path(result["input"]).name
            print(f"  [{i}/{total}] {status_icon} {filename} → {result['time']}s")

            if result["status"] == "success":
                success += 1
            else:
                errors += 1
                if result["error"]:
                    print(f"         Error: {result['error'][:100]}")

    total_time = round(time.time() - total_time_start, 1)
    print("\n" + "=" * 60)
    print(f"📊 KẾT QUẢ:")
    print(f"   ✅ Thành công: {success}/{total}")
    print(f"   ❌ Lỗi:       {errors}/{total}")
    print(f"   ⏱️  Tổng thời gian: {total_time}s")
    print(f"   📁 Output: {output_dir}/")
    print("=" * 60)

    # Telegram
    try:
        import json as _json
        if os.path.exists("config.json"):
            with open("config.json", "r", encoding="utf-8") as f:
                app_config = _json.load(f)
            tg = app_config.get("telegram", {})
            bot_token = tg.get("bot_token", "")
            chat_id = tg.get("chat_id", "")
            if bot_token and chat_id and "YOUR_" not in bot_token:
                from vtool.notify import send_telegram
                msg = (
                    f"📝 <b>Replace Subtitle hoàn thành!</b>\n"
                    f"✅ Thành công: {success}/{total}\n"
                    f"❌ Lỗi: {errors}/{total}\n"
                    f"⏱️ Thời gian: {total_time}s"
                )
                send_telegram(msg, bot_token, chat_id)
    except Exception:
        pass
