"""
Color Key processor - Thay nền video bằng color key.

Logic FFmpeg:
1. Scale background cho vừa kích thước video gốc
2. Dùng colorkey filter xoá màu nền khỏi video gốc
3. Overlay video gốc (đã xoá nền) lên background
4. Giữ nguyên audio từ video gốc

Dùng cho: video LINE chat, video có nền đồng màu.
"""

import os
import sys
import random
import subprocess
import time
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor, as_completed

from vtool.core.ffmpeg import (
    VIDEO_EXTENSIONS, IMAGE_EXTENSIONS,
    get_video_dimensions, list_media_files
)
from vtool.replace_bg_colorkey.config import ColorKeyConfig


def process_single_colorkey(args: tuple) -> dict:
    """
    Xử lý 1 video: dùng color key xoá nền, overlay lên background mới.
    """
    video_path, background_path, output_path, config = args

    start_time = time.time()
    result = {
        "input": video_path,
        "output": output_path,
        "status": "success",
        "error": None,
    }

    try:
        # Lấy thông tin video gốc
        width, height, duration, fps = get_video_dimensions(video_path)

        # Xác định background type
        bg_ext = Path(background_path).suffix.lower()
        is_video_bg = bg_ext in VIDEO_EXTENSIONS

        # Chọn codec
        hw_decode = []
        if config.use_gpu:
            import platform
            system = platform.system()
            if system == "Darwin":
                vcodec = "h264_videotoolbox"
                extra_params = ["-q:v", "65"]
            elif system == "Windows":
                vcodec = "h264_nvenc"
                extra_params = ["-preset", "p4", "-cq", str(config.crf)]
            else:
                vcodec = "h264_nvenc"
                extra_params = ["-preset", "p4", "-cq", str(config.crf)]
        else:
            vcodec = config.video_codec
            extra_params = ["-preset", config.preset, "-crf", str(config.crf)]

        # Filter complex: colorkey + overlay
        # 1. Scale background full frame
        # 2. Colorkey: xoá màu nền từ video gốc → transparent
        # 3. Overlay video gốc (foreground) lên background
        color = config.color
        similarity = config.similarity
        blend = config.blend

        if config.resolution:
            target_h = config.resolution
            target_w = int(width * target_h / height)
            target_w = target_w if target_w % 2 == 0 else target_w + 1
            scale_output = f"[composited]scale={target_w}:{target_h}[out]"
            filter_complex = (
                f"[1:v]scale={width}:{height}:force_original_aspect_ratio=increase,"
                f"crop={width}:{height}[bg];"
                f"[0:v]colorkey={color}:{similarity}:{blend}[fg];"
                f"[bg][fg]overlay=0:0[composited];"
                f"{scale_output}"
            )
        else:
            filter_complex = (
                f"[1:v]scale={width}:{height}:force_original_aspect_ratio=increase,"
                f"crop={width}:{height}[bg];"
                f"[0:v]colorkey={color}:{similarity}:{blend}[fg];"
                f"[bg][fg]overlay=0:0[out]"
            )

        # Build FFmpeg command
        if is_video_bg:
            input_bg_args = ["-stream_loop", "-1", "-i", background_path]
        else:
            input_bg_args = ["-loop", "1", "-i", background_path]

        # Tạo output dir
        os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else ".", exist_ok=True)

        cmd = [
            "ffmpeg", "-y",
            *hw_decode,
            "-i", video_path,
            *input_bg_args,
            "-filter_complex", filter_complex,
            "-map", "[out]", "-map", "0:a?",
            "-c:v", vcodec,
            *extra_params,
            "-c:a", config.audio_codec,
            "-b:a", "128k",
            "-t", str(duration),
            "-shortest",
            output_path
        ]

        # Chạy FFmpeg
        proc = subprocess.run(
            cmd, capture_output=True, text=True,
            timeout=3600, encoding="utf-8", errors="replace"
        )

        if proc.returncode != 0:
            result["status"] = "error"
            stderr_lines = proc.stderr.split("\n")
            error_lines = [l for l in stderr_lines if any(
                k in l.lower() for k in
                ["error", "invalid", "no such", "does not", "failed", "cannot", "not found"]
            )]
            if error_lines:
                result["error"] = "\n".join(error_lines[-5:])
            else:
                result["error"] = "\n".join(stderr_lines[-5:])

    except Exception as e:
        result["status"] = "error"
        result["error"] = str(e)

    result["time"] = round(time.time() - start_time, 1)
    return result


def batch_process_colorkey(config: ColorKeyConfig):
    """Xử lý hàng loạt video bằng color key."""

    # Tạo output dir
    os.makedirs(config.output_dir, exist_ok=True)

    # Lấy danh sách video input
    input_videos = list_media_files(config.input_dir, VIDEO_EXTENSIONS)
    if not input_videos:
        print(f"❌ Không tìm thấy video nào trong '{config.input_dir}/'")
        sys.exit(1)

    # Giới hạn số video
    if config.limit:
        input_videos = input_videos[:config.limit]

    # Lấy danh sách backgrounds
    backgrounds = list_media_files(config.background_dir, VIDEO_EXTENSIONS | IMAGE_EXTENSIONS)
    if not backgrounds:
        print(f"❌ Không tìm thấy background nào trong '{config.background_dir}/'")
        sys.exit(1)

    # Header
    print("=" * 60)
    print("🎨 REPLACE BACKGROUND (COLOR KEY)")
    print("=" * 60)
    print(f"📂 Input videos:  {len(input_videos)} files")
    print(f"🖼️  Backgrounds:   {len(backgrounds)} files")
    print(f"⚙️  Workers:       {config.max_workers} parallel")
    print(f"🎨 Color:         {config.color}")
    print(f"🔍 Similarity:    {config.similarity}")
    print(f"🌫️  Blend:         {config.blend}")
    print(f"🎥 Codec:         {config.video_codec} | CRF: {config.crf}")
    print(f"🚀 GPU:           {'ON' if config.use_gpu else 'OFF'}")
    print("=" * 60)

    # Chuẩn bị tasks
    tasks = []
    skipped = 0
    for video_path in input_videos:
        bg = random.choice(backgrounds)
        stem = Path(video_path).stem
        output_name = f"{stem}.{config.output_format}"
        output_path = os.path.join(config.output_dir, output_name)

        # Skip nếu output đã tồn tại
        if os.path.exists(output_path):
            skipped += 1
            continue

        tasks.append((video_path, bg, output_path, config))

        # Copy metadata
        input_dir = str(Path(video_path).parent)
        for ext in [".json", ".jpg"]:
            meta_src = os.path.join(input_dir, f"{stem}{ext}")
            if os.path.exists(meta_src):
                import shutil
                meta_dst = os.path.join(config.output_dir, f"{stem}{ext}")
                if not os.path.exists(meta_dst):
                    shutil.copy2(meta_src, meta_dst)

    if skipped > 0:
        print(f"⏭️  Bỏ qua {skipped} video đã có trong output")

    # Xử lý
    total = len(tasks)
    if total == 0:
        print("✅ Tất cả video đã được xử lý!")
        return

    success = 0
    errors = 0
    total_time_start = time.time()

    print(f"\n🚀 Bắt đầu xử lý {total} video...\n")

    with ProcessPoolExecutor(max_workers=config.max_workers) as executor:
        futures = {executor.submit(process_single_colorkey, task): task for task in tasks}

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

    # Summary
    total_time = round(time.time() - total_time_start, 1)
    print("\n" + "=" * 60)
    print(f"📊 KẾT QUẢ:")
    print(f"   ✅ Thành công: {success}/{total}")
    print(f"   ❌ Lỗi:       {errors}/{total}")
    print(f"   ⏱️  Tổng thời gian: {total_time}s")
    print(f"   📁 Output: {config.output_dir}/")
    print("=" * 60)

    # Telegram notification
    try:
        import json as _json
        config_path = "config.json"
        if os.path.exists(config_path):
            with open(config_path, "r", encoding="utf-8") as f:
                app_config = _json.load(f)
            tg = app_config.get("telegram", {})
            bot_token = tg.get("bot_token", "")
            chat_id = tg.get("chat_id", "")
            if bot_token and chat_id and "YOUR_" not in bot_token:
                from vtool.notify import send_telegram
                msg = (
                    f"🎨 <b>Color Key Replace hoàn thành!</b>\n"
                    f"✅ Thành công: {success}/{total}\n"
                    f"❌ Lỗi: {errors}/{total}\n"
                    f"⏱️ Thời gian: {total_time}s"
                )
                send_telegram(msg, bot_token, chat_id)
    except Exception:
        pass
