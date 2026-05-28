"""
VTool CLI - Entry point cho tất cả commands.

Usage:
    python -m vtool replace-bg [options]
    python -m vtool get-urls --channel URL
    python -m vtool download-yt --list urls.txt
    python -m vtool distribute --profiles "P1,P2" --per-day 7
    python -m vtool upload-gpm
    python -m vtool status
    python -m vtool --help
"""

import argparse
import sys


def cmd_replace_bg(args):
    """Command: Thay nền video hàng loạt."""
    from vtool.replace_bg import batch_process, ReplaceBgConfig

    config = ReplaceBgConfig(
        input_dir=args.input,
        background_dir=args.backgrounds,
        output_dir=args.output,
        max_workers=args.workers,
        auto_detect=not args.no_detect,
        text_ratio=args.text_ratio,
        preset=args.preset,
        crf=args.crf,
        use_gpu=args.gpu,
        output_format=args.format,
        limit=args.limit,
        resolution=args.resolution,
    )

    # Validate directories
    import os
    if not os.path.isdir(config.input_dir):
        print(f"❌ Thư mục input không tồn tại: {config.input_dir}")
        print(f"   Tạo thư mục và bỏ video vào: mkdir {config.input_dir}")
        sys.exit(1)

    if not os.path.isdir(config.background_dir):
        print(f"❌ Thư mục backgrounds không tồn tại: {config.background_dir}")
        print(f"   Tạo thư mục và bỏ ảnh/video nền vào: mkdir {config.background_dir}")
        sys.exit(1)

    batch_process(config)


def cmd_get_urls(args):
    """Command: Lấy URL video từ channel YouTube."""
    from vtool.download_yt import get_channel_urls

    get_channel_urls(
        channel_url=args.channel,
        limit=args.limit,
        output_file=args.output,
    )


def cmd_download_yt(args):
    """Command: Tải video từ YouTube."""
    from vtool.download_yt import download_videos

    # Đọc URLs
    if args.url:
        urls = [args.url]
    elif args.list:
        with open(args.list, "r", encoding="utf-8") as f:
            urls = [line.strip() for line in f if line.strip()]
    else:
        print("❌ Cần --url hoặc --list")
        sys.exit(1)

    if args.limit:
        urls = urls[:args.limit]

    download_videos(urls, output_dir=args.output, quality=args.quality)


def cmd_get_twitch_urls(args):
    """Command: Lấy URL VOD từ channel Twitch."""
    from vtool.download_twitch import get_twitch_vods

    get_twitch_vods(
        channel_url=args.channel,
        limit=args.limit,
        output_file=args.output,
    )


def cmd_download_twitch(args):
    """Command: Tải video từ Twitch + cắt thành từng đoạn."""
    from vtool.download_twitch import download_twitch_videos

    # Đọc URLs
    if args.url:
        urls = [args.url]
    elif args.list:
        with open(args.list, "r", encoding="utf-8") as f:
            urls = [line.strip() for line in f if line.strip()]
    else:
        print("❌ Cần --url hoặc --list")
        sys.exit(1)

    if args.limit:
        urls = urls[:args.limit]

    download_twitch_videos(
        urls,
        output_dir=args.output,
        quality=args.quality,
        split_hours=args.split,
    )


def cmd_distribute(args):
    """Command: Phân phối video vào folder theo ngày."""
    from vtool.distribute import distribute_videos

    profiles = [p.strip() for p in args.profiles.split(",")]

    distribute_videos(
        input_dir=args.input,
        output_dir=args.output,
        profiles=profiles,
        per_day=args.per_day,
        gap_days=args.gap,
        start_date=args.start_date,
        append=args.append,
    )


def cmd_replace_bg_colorkey(args):
    """Command: Thay nền video bằng color key."""
    from vtool.replace_bg_colorkey import batch_process_colorkey, ColorKeyConfig

    config = ColorKeyConfig(
        input_dir=args.input,
        background_dir=args.backgrounds,
        output_dir=args.output,
        max_workers=args.workers,
        crf=args.crf,
        use_gpu=args.gpu,
        output_format=args.format,
        color=args.color,
        similarity=args.similarity,
        blend=args.blend,
        limit=args.limit,
        resolution=args.resolution,
    )

    # Validate directories
    import os
    if not os.path.isdir(config.input_dir):
        print(f"❌ Thư mục input không tồn tại: {config.input_dir}")
        sys.exit(1)

    if not os.path.isdir(config.background_dir):
        print(f"❌ Thư mục backgrounds không tồn tại: {config.background_dir}")
        sys.exit(1)

    batch_process_colorkey(config)


def cmd_upload_gpm(args):
    """Command: Upload video lên YouTube qua GPM-Login."""
    from vtool.upload_gpm import upload_daily

    profiles_map = None
    if args.profiles_map:
        profiles_map = {}
        for pair in args.profiles_map.split(","):
            parts = pair.strip().split(":")
            if len(parts) == 2:
                profiles_map[parts[0].strip()] = parts[1].strip()

    # Parse publish times
    publish_times = None
    if args.times:
        publish_times = [t.strip() for t in args.times.split(",")]

    # Parse --date (ngày cụ thể hoặc số ngày)
    days = args.days
    target_date = None
    if args.date:
        target_date = args.date

    upload_daily(
        schedule_dir=args.schedule,
        config_path=args.config,
        days=days,
        target_date=target_date,
        visibility=args.visibility,
        publish_times=publish_times,
        profiles_map=profiles_map,
        gpm_port=args.port if args.port else None,
    )


def cmd_list_profiles(args):
    """Command: Liệt kê GPM profiles."""
    from vtool.upload_gpm import list_gpm_profiles
    list_gpm_profiles(gpm_port=args.port)


def cmd_status(args):
    """Command: Xem tiến độ upload các kênh."""
    import json
    import os
    from datetime import datetime

    schedule_file = os.path.join(args.schedule, "schedule.json")
    if not os.path.exists(schedule_file):
        print(f"❌ Không tìm thấy {schedule_file}")
        print("   Chạy 'python run.py distribute' trước.")
        sys.exit(1)

    with open(schedule_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    today = datetime.now().strftime("%Y-%m-%d")
    schedule = data["schedule"]

    print("=" * 60)
    print(f"📊 TRẠNG THÁI - {today}")
    print("=" * 60)
    print(f"📅 Ngày bắt đầu: {data.get('start_date', 'N/A')}")
    print(f"📦 Per day: {data.get('per_day', 7)} video/kênh")
    print(f"🔄 Gap: {data.get('gap_days', 10)} ngày")
    print("=" * 60)

    for profile_name, days in schedule.items():
        sorted_dates = sorted(days.keys())
        if not sorted_dates:
            continue

        # Đếm ngày đã qua
        past_days = sum(1 for d in sorted_dates if d <= today)
        total_days = len(sorted_dates)
        remaining = total_days - past_days
        total_videos = sum(len(v) for v in days.values())
        uploaded_videos = sum(len(days[d]) for d in sorted_dates if d <= today)

        start_date = sorted_dates[0]
        end_date = sorted_dates[-1]

        print(f"\n  👤 {profile_name}:")
        print(f"     📅 Ngày {past_days}/{total_days}")
        print(f"     🎬 Video: {uploaded_videos}/{total_videos}")
        print(f"     📆 {start_date} → {end_date}")
        print(f"     ⏳ Còn lại: {remaining} ngày")

        # Video hôm nay
        if today in days:
            print(f"     📋 Hôm nay: {len(days[today])} video cần upload")
            for v in days[today][:3]:
                print(f"        - {v}")
            if len(days[today]) > 3:
                print(f"        ... và {len(days[today]) - 3} video nữa")
        else:
            print(f"     ✅ Hôm nay: không có video")

    print("\n" + "=" * 60)

    # Hiển thị log gần nhất
    log_file = os.path.join(args.schedule, "upload_log.txt")
    if os.path.exists(log_file):
        print(f"\n📋 Log gần nhất ({log_file}):")
        with open(log_file, "r", encoding="utf-8") as f:
            lines = f.readlines()
            # Lấy 10 dòng cuối
            for line in lines[-10:]:
                print(f"   {line.rstrip()}")


def cmd_detect(args):
    """Command: Detect text region trong video."""
    from vtool.core.detector import detect_text_region

    video_path = args.video
    print(f"🔍 Detecting text region in: {video_path}")
    print("-" * 40)

    result = detect_text_region(video_path)

    print(f"  Text ratio:  {result['text_ratio']:.2%}")
    print(f"  Text Y:      {result['text_y']}px (of {result['height']}px)")
    print(f"  Confidence:  {result['confidence']:.0%}")
    print(f"  Method:      {result['method']}")
    print("-" * 40)

    if result["confidence"] < 0.5:
        print("⚠️  Low confidence. Có thể cần điều chỉnh --text-ratio thủ công.")


def cmd_check(args):
    """Command: Check tất cả video trong folder xem file nào bị lỗi."""
    import subprocess
    from pathlib import Path
    from vtool.core.ffmpeg import VIDEO_EXTENSIONS

    folder = args.folder
    print(f"🔍 Checking videos in: {folder}/")
    print("=" * 60)

    good = []
    bad = []

    files = sorted(Path(folder).iterdir())
    videos = [f for f in files if f.suffix.lower() in VIDEO_EXTENSIONS]

    for i, f in enumerate(videos, 1):
        cmd = [
            "ffprobe", "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "stream=width,height,duration",
            "-of", "csv=p=0",
            str(f)
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")

        if result.returncode != 0 or not result.stdout.strip():
            bad.append(f.name)
            print(f"  [{i}/{len(videos)}] ❌ {f.name}")
            if result.stderr.strip():
                print(f"           {result.stderr.strip()[:100]}")
        else:
            good.append(f.name)
            print(f"  [{i}/{len(videos)}] ✅ {f.name}")

    print("\n" + "=" * 60)
    print(f"📊 KẾT QUẢ:")
    print(f"   ✅ OK: {len(good)}")
    print(f"   ❌ Lỗi: {len(bad)}")

    if bad:
        print(f"\n❌ Danh sách file lỗi:")
        for name in bad:
            print(f"   - {name}")

    print("=" * 60)


def cmd_info(args):
    """Command: Hiển thị thông tin tool."""
    from vtool import __version__, __app_name__
    print(f"{__app_name__} v{__version__}")
    print()
    print("Available commands:")
    print("  get-urls         Lấy danh sách URL video từ channel YouTube")
    print("  download-yt      Tải video + metadata + thumbnail từ YouTube")
    print("  get-twitch-urls  Lấy danh sách VOD URL từ channel Twitch")
    print("  download-twitch  Tải video Twitch + cắt thành từng đoạn 1 tiếng")
    print("  replace-bg       Thay nền video hàng loạt, giữ text transcript")
    print("  distribute       Chia video vào folder theo ngày cho từng kênh")
    print("  upload-gpm       Upload video lên YouTube qua GPM-Login (hẹn giờ)")
    print("  list-profiles    Liệt kê GPM profiles (lấy ID cho config.json)")
    print("  status           Xem tiến độ upload các kênh")
    print("  detect           Auto-detect vùng text trong video")
    print()
    print("Flow:")
    print("  get-urls → download-yt → replace-bg → distribute → upload-gpm")
    print()
    print("Quick start:")
    print("  1. python run.py list-profiles          (lấy GPM ID)")
    print("  2. Sửa config.json (set GPM ID + giờ)")
    print("  3. python run.py get-urls --channel URL")
    print("  4. python run.py download-yt --list urls.txt")
    print("  5. python run.py replace-bg")
    print("  6. python run.py distribute --profiles 'K1,K2,K3,K4,K5'")
    print("  7. python run.py upload-gpm             (upload hôm nay)")
    print("  7. python run.py upload-gpm --days 5    (upload trước 5 ngày)")
    print()
    print("Run 'python -m vtool <command> --help' for details.")


def main():
    parser = argparse.ArgumentParser(
        prog="vtool",
        description="VTool - Video Processing & Reup Toolkit"
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # === Command: get-urls ===
    p_urls = subparsers.add_parser(
        "get-urls",
        help="Lấy danh sách URL video từ channel YouTube"
    )
    p_urls.add_argument("--channel", required=True, help="URL channel hoặc playlist YouTube")
    p_urls.add_argument("--limit", type=int, default=None, help="Giới hạn số video")
    p_urls.add_argument("--output", default="urls.txt", help="File output (default: urls.txt)")
    p_urls.set_defaults(func=cmd_get_urls)

    # === Command: download-yt ===
    p_download = subparsers.add_parser(
        "download-yt",
        help="Tải video + metadata + thumbnail từ YouTube"
    )
    p_download.add_argument("--url", help="URL 1 video")
    p_download.add_argument("--list", help="File chứa danh sách URL (mỗi dòng 1 URL)")
    p_download.add_argument("--output", default="input_videos", help="Thư mục output")
    p_download.add_argument("--quality", default="best", choices=["best", "1080", "720"],
                            help="Chất lượng video (default: best)")
    p_download.add_argument("--limit", type=int, default=None, help="Giới hạn số video tải")
    p_download.set_defaults(func=cmd_download_yt)

    # === Command: get-twitch-urls ===
    p_twitch_urls = subparsers.add_parser(
        "get-twitch-urls",
        help="Lấy danh sách VOD URL từ channel Twitch"
    )
    p_twitch_urls.add_argument("--channel", required=True, help="URL channel Twitch")
    p_twitch_urls.add_argument("--limit", type=int, default=None, help="Giới hạn số VOD")
    p_twitch_urls.add_argument("--output", default="twitch_urls.txt", help="File output")
    p_twitch_urls.set_defaults(func=cmd_get_twitch_urls)

    # === Command: download-twitch ===
    p_twitch = subparsers.add_parser(
        "download-twitch",
        help="Tải video Twitch + cắt thành từng đoạn 1 tiếng → backgrounds/"
    )
    p_twitch.add_argument("--url", help="URL 1 VOD/clip")
    p_twitch.add_argument("--list", help="File chứa danh sách URL")
    p_twitch.add_argument("--output", default="backgrounds", help="Thư mục output (default: backgrounds)")
    p_twitch.add_argument("--quality", default="best", choices=["best", "1080", "720"],
                          help="Chất lượng video (default: best)")
    p_twitch.add_argument("--split", type=float, default=1.0,
                          help="Cắt mỗi đoạn bao nhiêu giờ (default: 1.0)")
    p_twitch.add_argument("--limit", type=int, default=None, help="Giới hạn số video tải")
    p_twitch.set_defaults(func=cmd_download_twitch)

    # === Command: replace-bg ===
    p_replace = subparsers.add_parser(
        "replace-bg",
        help="Thay nền video hàng loạt, giữ text transcript"
    )
    p_replace.add_argument("--input", default="input_videos", help="Thư mục video input")
    p_replace.add_argument("--backgrounds", default="backgrounds", help="Thư mục backgrounds")
    p_replace.add_argument("--output", default="output_videos", help="Thư mục output")
    p_replace.add_argument("--workers", type=int, default=4, help="Số worker song song (default: 4)")
    p_replace.add_argument("--text-ratio", type=float, default=0.30,
                           help="Tỷ lệ text bar fallback (default: 0.30)")
    p_replace.add_argument("--no-detect", action="store_true",
                           help="Tắt auto-detect, dùng --text-ratio cố định")
    p_replace.add_argument("--preset", default="fast",
                           choices=["ultrafast", "superfast", "veryfast", "faster", "fast", "medium"],
                           help="FFmpeg preset (default: fast)")
    p_replace.add_argument("--crf", type=int, default=23, help="Chất lượng CRF 18-28 (default: 23)")
    p_replace.add_argument("--gpu", action="store_true",
                           help="Dùng GPU (Mac: videotoolbox, Win: nvenc, Linux: nvenc)")
    p_replace.add_argument("--format", default="mp4", help="Output format (default: mp4)")
    p_replace.add_argument("--limit", type=int, default=None, help="Giới hạn số video xử lý")
    p_replace.add_argument("--resolution", type=int, default=None,
                           choices=[720, 1080],
                           help="Scale output (720 hoặc 1080, default: giữ nguyên)")
    p_replace.set_defaults(func=cmd_replace_bg)

    # === Command: distribute ===
    p_dist = subparsers.add_parser(
        "distribute",
        help="Chia video vào folder theo ngày cho từng kênh"
    )

    # === Command: replace-bg-colorkey ===
    p_colorkey = subparsers.add_parser(
        "replace-bg-colorkey",
        help="Thay nền video bằng color key (cho video LINE chat, nền đồng màu)"
    )
    p_colorkey.add_argument("--input", default="input_videos", help="Thư mục video input")
    p_colorkey.add_argument("--backgrounds", default="backgrounds", help="Thư mục backgrounds")
    p_colorkey.add_argument("--output", default="output_videos", help="Thư mục output")
    p_colorkey.add_argument("--workers", type=int, default=2, help="Số worker (default: 2)")
    p_colorkey.add_argument("--color", default="0x2C3E50",
                            help="Màu nền cần xoá, hex RGB (default: 0x2C3E50 = xám đen LINE)")
    p_colorkey.add_argument("--similarity", type=float, default=0.3,
                            help="Độ tương đồng màu 0.0-1.0 (default: 0.3, cao=xoá nhiều)")
    p_colorkey.add_argument("--blend", type=float, default=0.1,
                            help="Độ mượt viền 0.0-1.0 (default: 0.1)")
    p_colorkey.add_argument("--crf", type=int, default=23, help="CRF 18-28 (default: 23)")
    p_colorkey.add_argument("--gpu", action="store_true", help="Dùng GPU NVIDIA")
    p_colorkey.add_argument("--format", default="mp4", help="Output format")
    p_colorkey.add_argument("--limit", type=int, default=None, help="Giới hạn số video")
    p_colorkey.add_argument("--resolution", type=int, default=None,
                            choices=[720, 1080], help="Scale output (720/1080)")
    p_colorkey.set_defaults(func=cmd_replace_bg_colorkey)
    p_dist.add_argument("--input", default="output_videos", help="Thư mục video đã thay nền")
    p_dist.add_argument("--output", default="schedules", help="Thư mục output schedule")
    p_dist.add_argument("--profiles", default="channel_1",
                        help="Tên các kênh, cách nhau bằng dấu phẩy (vd: 'K1,K2,K3')")
    p_dist.add_argument("--per-day", type=int, default=7, help="Số video mỗi ngày (default: 7)")
    p_dist.add_argument("--gap", type=int, default=10,
                        help="Số ngày tối thiểu video trùng giữa các kênh (default: 10)")
    p_dist.add_argument("--start-date", default=None,
                        help="Ngày bắt đầu YYYY-MM-DD (default: hôm nay)")
    p_dist.add_argument("--append", action="store_true",
                        help="Nối thêm video mới vào schedule cũ (không ghi đè)")
    p_dist.set_defaults(func=cmd_distribute)

    # === Command: upload-gpm ===
    p_upload = subparsers.add_parser(
        "upload-gpm",
        help="Upload video lên YouTube qua GPM-Login"
    )
    p_upload.add_argument("--schedule", default="schedules", help="Thư mục schedule")
    p_upload.add_argument("--config", default="config.json", help="File config (default: config.json)")
    p_upload.add_argument("--days", type=int, default=1,
                          help="Số ngày upload (1=hôm nay, 5=hôm nay + 4 ngày tới)")
    p_upload.add_argument("--date", default=None,
                          help="Ngày cụ thể cần upload (format: 2026-05-30 hoặc 30/05/2026)")
    p_upload.add_argument("--profiles-map", default=None,
                          help="Map kênh:GPM_ID (override config.json)")
    p_upload.add_argument("--visibility", default=None,
                          choices=["public", "unlisted", "private", "schedule"],
                          help="Visibility (default: schedule = hẹn giờ)")
    p_upload.add_argument("--times", default=None,
                          help="Giờ publish, override config.json "
                               "(vd: '08:00,10:00,12:00,14:00,16:00,18:00,20:00')")
    p_upload.add_argument("--port", type=int, default=None, help="GPM API port (override config.json)")
    p_upload.set_defaults(func=cmd_upload_gpm)

    # === Command: list-profiles ===
    p_list = subparsers.add_parser(
        "list-profiles",
        help="Liệt kê tất cả GPM-Login profiles (lấy ID để set config)"
    )
    p_list.add_argument("--port", type=int, default=19995, help="GPM API port")
    p_list.set_defaults(func=cmd_list_profiles)

    # === Command: status ===
    p_status = subparsers.add_parser(
        "status",
        help="Xem tiến độ upload các kênh"
    )
    p_status.add_argument("--schedule", default="schedules", help="Thư mục schedule")
    p_status.set_defaults(func=cmd_status)

    # === Command: detect ===
    p_detect = subparsers.add_parser(
        "detect",
        help="Auto-detect vùng text trong video"
    )
    p_detect.add_argument("video", help="Đường dẫn video cần detect")
    p_detect.set_defaults(func=cmd_detect)

    # === Command: check ===
    p_check = subparsers.add_parser(
        "check",
        help="Check video nào bị lỗi trong folder"
    )
    p_check.add_argument("folder", nargs="?", default="backgrounds",
                         help="Folder cần check (default: backgrounds)")
    p_check.set_defaults(func=cmd_check)

    # Parse
    args = parser.parse_args()

    if args.command is None:
        cmd_info(args)
    else:
        args.func(args)


if __name__ == "__main__":
    main()
