"""
Core processor for replacing video backgrounds.
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
from vtool.replace_bg.config import ReplaceBgConfig


def _detect_or_fallback(video_path: str, config: ReplaceBgConfig) -> float:
    """Detect text ratio hoặc dùng fallback."""
    if not config.auto_detect:
        return config.text_ratio

    try:
        from vtool.core.detector import detect_text_region
        result = detect_text_region(video_path, config.detect_sample_times)

        if result["confidence"] >= 0.3:
            return result["text_ratio"]
        else:
            return config.text_ratio
    except ImportError:
        # OpenCV chưa cài → dùng fallback
        return config.text_ratio
    except Exception:
        return config.text_ratio


def process_single_video(args: tuple) -> dict:
    """
    Xử lý 1 video: thay background, giữ text bar.

    Logic FFmpeg:
    1. Crop phần text bar (phần dưới) từ video gốc
    2. Scale/crop background cho vừa phần trên
    3. vstack 2 phần lại
    4. Giữ nguyên audio
    """
    video_path, background_path, output_path, config = args

    start_time = time.time()
    result = {
        "input": video_path,
        "output": output_path,
        "status": "success",
        "error": None,
        "text_ratio": None,
    }

    try:
        # Lấy thông tin video gốc
        width, height, duration, fps = get_video_dimensions(video_path)

        # Detect text region
        text_ratio = _detect_or_fallback(video_path, config)
        result["text_ratio"] = text_ratio

        # Tính toán vùng
        text_height = int(height * text_ratio)
        bg_height = height - text_height

        # Xác định background type
        bg_ext = Path(background_path).suffix.lower()
        is_video_bg = bg_ext in VIDEO_EXTENSIONS

        # Chọn codec + hardware acceleration
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
                hw_decode = []  # 1660 Ti không decode AV1, để CPU decode
            else:
                vcodec = "h264_nvenc"
                extra_params = ["-preset", "p4", "-cq", str(config.crf)]
                hw_decode = ["-hwaccel", "cuda"]
        else:
            vcodec = config.video_codec
            extra_params = ["-preset", config.preset, "-crf", str(config.crf)]

        # Filter complex: scale bg full frame → overlay text bar sát mép dưới
        # Nếu có overlay_opacity: thêm lớp đen mờ lên text bar
        opacity = config.overlay_opacity if hasattr(config, 'overlay_opacity') and config.overlay_opacity else 0

        # Mode: lumakey = giữ text trắng, xoá nền tối
        if config.mode == "lumakey":
            if config.resolution:
                target_h = config.resolution
                target_w = int(width * target_h / height)
                target_w = target_w if target_w % 2 == 0 else target_w + 1
                filter_complex = (
                    f"[1:v]scale={width}:{height}:force_original_aspect_ratio=increase,"
                    f"crop={width}:{height}[bg];"
                    f"[0:v]lumakey=threshold=0.7:tolerance=0.2:softness=0.1[fg];"
                    f"[bg][fg]overlay=0:0[composited];"
                    f"[composited]scale={target_w}:{target_h}[out]"
                )
            else:
                filter_complex = (
                    f"[1:v]scale={width}:{height}:force_original_aspect_ratio=increase,"
                    f"crop={width}:{height}[bg];"
                    f"[0:v]lumakey=threshold=0.7:tolerance=0.2:softness=0.1[fg];"
                    f"[bg][fg]overlay=0:0[out]"
                )
        elif config.resolution:
            target_h = config.resolution
            target_w = int(width * target_h / height)
            target_w = target_w if target_w % 2 == 0 else target_w + 1
            
            if opacity > 0:
                # Dùng drawbox để vẽ hộp đen mờ lên phần text bar
                alpha = opacity
                filter_complex = (
                    f"[1:v]scale={width}:{height}:force_original_aspect_ratio=increase,"
                    f"crop={width}:{height}[bg];"
                    f"[0:v]crop={width}:{text_height}:0:{height - text_height},"
                    f"drawbox=x=0:y=0:w={width}:h={text_height}:color=black@{alpha}:t=fill[darktext];"
                    f"[bg][darktext]overlay=0:{height - text_height}[composited];"
                    f"[composited]scale={target_w}:{target_h}[out]"
                )
            else:
                filter_complex = (
                    f"[1:v]scale={width}:{height}:force_original_aspect_ratio=increase,"
                    f"crop={width}:{height}[bg];"
                    f"[0:v]crop={width}:{text_height}:0:{height - text_height}[text];"
                    f"[bg][text]overlay=0:{height - text_height}[composited];"
                    f"[composited]scale={target_w}:{target_h}[out]"
                )
        else:
            if opacity > 0:
                alpha = opacity
                filter_complex = (
                    f"[1:v]scale={width}:{height}:force_original_aspect_ratio=increase,"
                    f"crop={width}:{height}[bg];"
                    f"[0:v]crop={width}:{text_height}:0:{height - text_height},"
                    f"drawbox=x=0:y=0:w={width}:h={text_height}:color=black@{alpha}:t=fill[darktext];"
                    f"[bg][darktext]overlay=0:{height - text_height}[out]"
                )
            else:
                filter_complex = (
                    f"[1:v]scale={width}:{height}:force_original_aspect_ratio=increase,"
                    f"crop={width}:{height}[bg];"
                    f"[0:v]crop={width}:{text_height}:0:{height - text_height}[text];"
                    f"[bg][text]overlay=0:{height - text_height}[out]"
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
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=3600, encoding="utf-8", errors="replace")

        if proc.returncode != 0:
            result["status"] = "error"
            stderr_lines = proc.stderr.split("\n")
            error_lines = [l for l in stderr_lines if any(k in l.lower() for k in ["error", "invalid", "no such", "does not", "failed", "cannot", "not found"])]
            if error_lines:
                result["error"] = "\n".join(error_lines[-5:])
            else:
                result["error"] = "\n".join(stderr_lines[-5:])

    except Exception as e:
        result["status"] = "error"
        result["error"] = str(e)

    result["time"] = round(time.time() - start_time, 1)
    return result


def batch_process(config: ReplaceBgConfig):
    """Xử lý hàng loạt video song song."""

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
    print("🎬 REPLACE BACKGROUND - Batch Processing")
    print("=" * 60)
    print(f"📂 Input videos:  {len(input_videos)} files")
    print(f"🖼️  Backgrounds:   {len(backgrounds)} files")
    print(f"⚙️  Workers:       {config.max_workers} parallel")
    print(f"🔍 Auto-detect:   {'ON' if config.auto_detect else 'OFF'}")
    if not config.auto_detect:
        print(f"📐 Text ratio:    {config.text_ratio:.0%} (fixed)")
    print(f"🎥 Codec:         {config.video_codec} | Preset: {config.preset} | CRF: {config.crf}")
    print(f"🚀 GPU:           {'ON' if config.use_gpu else 'OFF'}")
    print("=" * 60)

    # Auto-detect trước cho video đầu tiên để hiển thị
    if config.auto_detect:
        try:
            from vtool.core.detector import detect_text_region
            sample_result = detect_text_region(input_videos[0], config.detect_sample_times)
            print(f"🔍 Sample detect: text_ratio={sample_result['text_ratio']:.2%}, "
                  f"confidence={sample_result['confidence']:.0%}, "
                  f"method={sample_result['method']}")
        except Exception as e:
            print(f"⚠️  Auto-detect failed, using fallback {config.text_ratio:.0%}: {e}")
        print("=" * 60)

    # Chuẩn bị tasks
    tasks = []
    skipped = 0
    for video_path in input_videos:
        bg = random.choice(backgrounds)
        stem = Path(video_path).stem
        # Bỏ prefix "new_" để giữ tên gốc
        output_name = f"{stem}.{config.output_format}"
        output_path = os.path.join(config.output_dir, output_name)
        
        # Skip nếu output đã tồn tại
        if os.path.exists(output_path):
            skipped += 1
            continue
        
        tasks.append((video_path, bg, output_path, config))

        # Copy metadata (.json, .jpg) sang output dir
        input_dir = str(Path(video_path).parent)
        for ext in [".json", ".jpg"]:
            meta_src = os.path.join(input_dir, f"{stem}{ext}")
            if os.path.exists(meta_src):
                import shutil
                meta_dst = os.path.join(config.output_dir, f"{stem}{ext}")
                shutil.copy2(meta_src, meta_dst)
    
    if skipped > 0:
        print(f"⏭️  Bỏ qua {skipped} video đã có trong output")

    # Xử lý song song
    total = len(tasks)
    success = 0
    errors = 0
    total_time_start = time.time()

    print(f"\n🚀 Bắt đầu xử lý {total} video...\n")

    with ProcessPoolExecutor(max_workers=config.max_workers) as executor:
        futures = {executor.submit(process_single_video, task): task for task in tasks}

        for i, future in enumerate(as_completed(futures), 1):
            result = future.result()
            status_icon = "✅" if result["status"] == "success" else "❌"
            filename = Path(result["input"]).name
            ratio_info = f" [text:{result['text_ratio']:.0%}]" if result["text_ratio"] else ""

            print(f"  [{i}/{total}] {status_icon} {filename}{ratio_info} → {result['time']}s")

            if result["status"] == "success":
                success += 1
            else:
                errors += 1
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

    # Gửi thông báo Telegram
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
                    f"🎬 <b>Replace BG hoàn thành!</b>\n"
                    f"✅ Thành công: {success}/{total}\n"
                    f"❌ Lỗi: {errors}/{total}\n"
                    f"⏱️ Thời gian: {total_time}s"
                )
                send_telegram(msg, bot_token, chat_id)
    except Exception:
        pass
