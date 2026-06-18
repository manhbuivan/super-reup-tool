"""
Text Mask processor - Detect chữ trắng và thay background.

Logic FFmpeg:
1. Scale background cho vừa kích thước video gốc
2. Tạo alpha mask từ video gốc: pixel sáng (chữ trắng) → giữ lại, pixel tối → transparent
3. Overlay video gốc (chỉ phần text trắng) lên background mới
4. Giữ nguyên audio từ video gốc

Kỹ thuật chính:
- Dùng `geq` filter để tạo alpha channel dựa trên luminance
- Pixel có brightness > threshold → opaque (giữ lại = text trắng)
- Pixel có brightness < threshold → transparent (xoá = background cũ)
- Kết hợp dilate/erosion để mask mượt hơn

Dùng cho: video có hardcoded subtitle trắng (Japanese, Chinese text) trên nền ảnh/video.
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
from vtool.replace_bg_textmask.config import TextMaskConfig


def _build_textmask_filter(width: int, height: int, config: TextMaskConfig) -> str:
    """
    Build FFmpeg filter complex cho text mask.
    
    Chiến lược:
    - Background mới full frame
    - Vẽ dải đen mờ (drawbox) phía dưới để text nổi
    - Dùng lumakey để xoá pixel tối (background) và giữ pixel sáng (text trắng)
    - Chỉ apply lumakey ở vùng text (phần dưới), phần trên dùng BG mới 100%
    - Overlay text trắng lên background mới
    
    Kết quả: BG mới + dải đen mờ + chữ trắng gốc. Hoàn toàn mới, không dính gì BG cũ.
    """
    threshold = config.threshold
    min_bright = config.min_brightness
    bar_opacity = config.bar_opacity
    bar_ratio = config.bar_ratio

    # Tính chiều cao dải đen
    bar_height = int(height * bar_ratio)
    bar_y = height - bar_height

    # Convert threshold 0-255 → lumakey parameters
    # FFmpeg lumakey: xoá pixel có luma GẦN threshold (trong khoảng threshold ± tolerance)
    # Ta muốn xoá pixel TỐI (nền đen/xám) → threshold thấp, tolerance cao
    # threshold=0: target pixel đen
    # tolerance: bao nhiêu luma range bị xoá (từ 0 đến tolerance*255 sẽ bị xoá)
    # Ví dụ: min_brightness=180 → xoá tất cả pixel có luma < 180/255 ≈ 0.7
    luma_threshold = 0.0  # Target: pixel đen (luma=0)
    luma_tolerance = min_bright / 255.0  # Xoá tất cả pixel từ 0 đến min_bright
    luma_softness = (threshold - min_bright) / 255.0  # Vùng fade mềm

    # Luôn crop phần dưới để tránh giữ nhầm vùng sáng ở phần trên (người, đồ vật...)
    # text_region=full vẫn chỉ lấy phần dưới theo bar_ratio (hoặc text_ratio)
    if config.text_region == "bottom":
        text_height = int(height * config.text_ratio)
    else:
        # Khi full, dùng bar_ratio để xác định vùng text (thường text ở phần dưới)
        text_height = int(height * config.bar_ratio)
    
    text_height = text_height if text_height % 2 == 0 else text_height + 1
    crop_y = height - text_height
    overlay_y = crop_y

    filter_parts = []

    # Step 1: Scale background full frame + drawbox đen mờ ở vùng text
    if bar_opacity > 0:
        filter_parts.append(
            f"[1:v]scale={width}:{height}:force_original_aspect_ratio=increase,"
            f"crop={width}:{height},"
            f"drawbox=x=0:y={bar_y}:w={width}:h={bar_height}:color=black@{bar_opacity}:t=fill[bg]"
        )
    else:
        filter_parts.append(
            f"[1:v]scale={width}:{height}:force_original_aspect_ratio=increase,"
            f"crop={width}:{height}[bg]"
        )

    # Step 2: Crop vùng text (phần dưới) từ video gốc, apply lumakey
    filter_parts.append(
        f"[0:v]crop={width}:{text_height}:0:{crop_y},"
        f"lumakey=threshold={luma_threshold}:tolerance={luma_tolerance}:softness={luma_softness}[textmasked]"
    )

    # Step 3: Overlay text lên BG ở vị trí phần dưới
    filter_parts.append(
        f"[bg][textmasked]overlay=0:{overlay_y}[out]"
    )

    return ";".join(filter_parts)


def process_single_textmask(args: tuple) -> dict:
    """
    Xử lý 1 video: detect text trắng, thay background.
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
                hw_decode = ["-hwaccel", "cuda"]
            else:
                vcodec = "h264_nvenc"
                extra_params = ["-preset", "p4", "-cq", str(config.crf)]
                hw_decode = ["-hwaccel", "cuda"]
        else:
            vcodec = config.video_codec
            extra_params = ["-preset", config.preset, "-crf", str(config.crf)]

        # Build filter complex
        filter_complex = _build_textmask_filter(width, height, config)

        # Resolution scale
        if config.resolution:
            target_h = config.resolution
            target_w = int(width * target_h / height)
            target_w = target_w if target_w % 2 == 0 else target_w + 1
            # Thêm scale vào cuối filter
            filter_complex = filter_complex.replace("[out]", f"[prescale];[prescale]scale={target_w}:{target_h}[out]")

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


def batch_process_textmask(config: TextMaskConfig):
    """Xử lý hàng loạt video bằng text mask."""

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
    print("🔤 REPLACE BACKGROUND (TEXT MASK)")
    print("=" * 60)
    print(f"📂 Input videos:  {len(input_videos)} files")
    print(f"🖼️  Backgrounds:   {len(backgrounds)} files")
    print(f"⚙️  Workers:       {config.max_workers} parallel")
    print(f"🔍 Threshold:     {config.threshold} (brightness)")
    print(f"🌫️  Softness:      min_bright={config.min_brightness}")
    print(f"📐 Text region:   {config.text_region}", end="")
    if config.text_region == "bottom":
        print(f" ({config.text_ratio:.0%})")
    else:
        print()
    print(f"🔲 Expand mask:   {config.expand}px")
    print(f"▪️  Black bar:     opacity={config.bar_opacity}, height={config.bar_ratio:.0%}")
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
        futures = {executor.submit(process_single_textmask, task): task for task in tasks}

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
                    print(f"         Error: {result['error'][:150]}")

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
                    f"🔤 <b>Text Mask Replace hoàn thành!</b>\n"
                    f"✅ Thành công: {success}/{total}\n"
                    f"❌ Lỗi: {errors}/{total}\n"
                    f"⏱️ Thời gian: {total_time}s"
                )
                send_telegram(msg, bot_token, chat_id)
    except Exception:
        pass
