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
    )


def cmd_upload_gpm(args):
    """Command: Upload video lên YouTube qua GPM-Login."""
    from vtool.upload_gpm import upload_daily

    profiles_map = None
    if args.profiles_map:
        # Format: "channel_1:gpm_id_1,channel_2:gpm_id_2"
        profiles_map = {}
        for pair in args.profiles_map.split(","):
            parts = pair.strip().split(":")
            if len(parts) == 2:
                profiles_map[parts[0].strip()] = parts[1].strip()

    upload_daily(
        schedule_dir=args.schedule,
        profiles_map=profiles_map,
        visibility=args.visibility,
        gpm_port=args.port,
    )


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


def cmd_info(args):
    """Command: Hiển thị thông tin tool."""
    from vtool import __version__, __app_name__
    print(f"{__app_name__} v{__version__}")
    print()
    print("Available commands:")
    print("  get-urls     Lấy danh sách URL video từ channel YouTube")
    print("  download-yt  Tải video + metadata + thumbnail từ YouTube")
    print("  replace-bg   Thay nền video hàng loạt, giữ text transcript")
    print("  distribute   Chia video vào folder theo ngày cho từng kênh")
    print("  upload-gpm   Upload video lên YouTube qua GPM-Login")
    print("  status       Xem tiến độ upload các kênh")
    print("  detect       Auto-detect vùng text trong video")
    print()
    print("Flow:")
    print("  get-urls → download-yt → replace-bg → distribute → upload-gpm")
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
    p_replace.set_defaults(func=cmd_replace_bg)

    # === Command: distribute ===
    p_dist = subparsers.add_parser(
        "distribute",
        help="Chia video vào folder theo ngày cho từng kênh"
    )
    p_dist.add_argument("--input", default="output_videos", help="Thư mục video đã thay nền")
    p_dist.add_argument("--output", default="schedules", help="Thư mục output schedule")
    p_dist.add_argument("--profiles", default="channel_1",
                        help="Tên các kênh, cách nhau bằng dấu phẩy (vd: 'K1,K2,K3')")
    p_dist.add_argument("--per-day", type=int, default=7, help="Số video mỗi ngày (default: 7)")
    p_dist.add_argument("--gap", type=int, default=10,
                        help="Số ngày tối thiểu video trùng giữa các kênh (default: 10)")
    p_dist.add_argument("--start-date", default=None,
                        help="Ngày bắt đầu YYYY-MM-DD (default: hôm nay)")
    p_dist.set_defaults(func=cmd_distribute)

    # === Command: upload-gpm ===
    p_upload = subparsers.add_parser(
        "upload-gpm",
        help="Upload video lên YouTube qua GPM-Login"
    )
    p_upload.add_argument("--schedule", default="schedules", help="Thư mục schedule")
    p_upload.add_argument("--profiles-map", default=None,
                          help="Map kênh:GPM_ID (vd: 'K1:abc-123,K2:def-456')")
    p_upload.add_argument("--visibility", default="public",
                          choices=["public", "unlisted", "private"],
                          help="Visibility (default: public)")
    p_upload.add_argument("--port", type=int, default=19995, help="GPM API port (default: 19995)")
    p_upload.set_defaults(func=cmd_upload_gpm)

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

    # Parse
    args = parser.parse_args()

    if args.command is None:
        cmd_info(args)
    else:
        args.func(args)


if __name__ == "__main__":
    main()
