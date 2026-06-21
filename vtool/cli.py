"""
VTool CLI - Entry point cho tất cả commands.

Usage:
    python -m vtool replace-bg [options]
    python -m vtool replace-bg-textmask [options]
    python -m vtool get-urls --channel URL
    python -m vtool download-yt --list urls.txt
    python -m vtool distribute --profiles "P1,P2" --per-day 7
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
        overlay_opacity=args.overlay_opacity,
        mode=args.mode,
        bottom_trim=args.bottom_trim,
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
    from vtool.get_channel_urls import get_channel_video_urls, save_urls

    print(f"🔍 Đang lấy danh sách video từ: {args.channel}")
    urls = get_channel_video_urls(args.channel, limit=args.limit)

    if not urls:
        print("❌ Không lấy được URL nào")
        sys.exit(1)

    save_urls(urls, args.output)
    print(f"✅ Lấy được {len(urls)} URL → lưu vào {args.output}")


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

    download_videos(urls, output_dir=args.output, quality=args.quality, subtitle=args.subtitle)


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


def cmd_download_subtitle(args):
    """Command: Tải subtitle từ YouTube."""
    from vtool.download_subtitle import download_subtitles

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

    languages = [l.strip() for l in args.lang.split(",")]
    download_subtitles(urls, output_dir=args.output, languages=languages)


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
        exclusive=args.exclusive,
        shuffle=args.shuffle,
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


def cmd_replace_bg_textmask(args):
    """Command: Thay nền video bằng text mask (giữ chữ trắng)."""
    from vtool.replace_bg_textmask import batch_process_textmask, TextMaskConfig

    config = TextMaskConfig(
        input_dir=args.input,
        background_dir=args.backgrounds,
        output_dir=args.output,
        max_workers=args.workers,
        crf=args.crf,
        preset=args.preset,
        use_gpu=args.gpu,
        output_format=args.format,
        threshold=args.threshold,
        softness=args.softness,
        expand=args.expand,
        text_region=args.text_region,
        text_ratio=args.text_ratio,
        min_brightness=args.min_brightness,
        bar_opacity=args.bar_opacity,
        bar_ratio=args.bar_ratio,
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

    batch_process_textmask(config)


def cmd_export_upload(args):
    """Command: Tạo file Excel upload list cho GPM Automate."""
    import json
    import os
    from datetime import datetime, timedelta
    from pathlib import Path

    schedule_file = os.path.join(args.schedule, "schedule.json")
    if not os.path.exists(schedule_file):
        print(f"❌ Không tìm thấy {schedule_file}")
        print("   Chạy 'python run.py distribute' trước.")
        sys.exit(1)

    with open(schedule_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    schedule = data["schedule"]

    # Load config
    config = {}
    if os.path.exists("config.json"):
        with open("config.json", "r", encoding="utf-8") as f:
            config = json.load(f)

    # Xác định profiles cần export
    if args.profile:
        profiles_to_export = [args.profile]
    else:
        profiles_to_export = list(schedule.keys())

    # Parse date
    if args.date:
        if "/" in args.date:
            start = datetime.strptime(args.date, "%d/%m/%Y")
        else:
            start = datetime.strptime(args.date, "%Y-%m-%d")
    else:
        start = datetime.now()

    # Get GPM profile names from API
    gpm_names = {}
    try:
        import requests
        gpm_host = config.get("gpm_host", "127.0.0.1")
        gpm_port = config.get("gpm_port", 19995)
        resp = requests.get(f"http://{gpm_host}:{gpm_port}/api/v3/profiles", timeout=5)
        if resp.status_code == 200:
            for p in resp.json().get("data", []):
                gpm_names[p.get("id", "")] = p.get("name", "")
            print(f"  ✅ GPM API: tìm thấy {len(gpm_names)} profiles")
        else:
            print(f"  ⚠️  GPM API trả về status {resp.status_code}")
    except Exception as e:
        print(f"  ⚠️  Không kết nối được GPM API: {e}")

    # Build rows cho tất cả profiles
    rows = []
    schedule_dir = args.schedule

    for profile_name in profiles_to_export:
        if profile_name not in schedule:
            print(f"⚠️  Profile '{profile_name}' không có trong schedule, skip")
            continue

        days_schedule = schedule[profile_name]

        # Collect dates cho profile này
        if args.all:
            upload_dates = sorted(days_schedule.keys())
        else:
            upload_dates = []
            for i in range(args.days):
                d = start + timedelta(days=i)
                upload_dates.append(d.strftime("%Y-%m-%d"))

        # Get publish times
        profile_config = config.get("profiles", {}).get(profile_name, {})
        publish_times = profile_config.get("publish_times",
                                           ["08:00", "10:00", "12:00", "14:00", "16:00", "18:00", "20:00"])

        # Get GPM profile name
        gpm_id = profile_config.get("gpm_id", "") if isinstance(profile_config, dict) else ""
        config_name = profile_config.get("name", "") if isinstance(profile_config, dict) else ""
        gpm_profile_name = gpm_names.get(gpm_id, config_name or profile_name)

        for date_str in upload_dates:
            if date_str not in days_schedule:
                continue

            videos = days_schedule[date_str]
            profile_dir = os.path.join(schedule_dir, profile_name)
            day_folder = None
            if os.path.exists(profile_dir):
                for folder in sorted(Path(profile_dir).iterdir()):
                    if folder.is_dir() and date_str in folder.name:
                        day_folder = str(folder)
                        break

            for idx, video_name in enumerate(videos):
                stem = Path(video_name).stem
                video_path = os.path.join(day_folder, video_name) if day_folder else ""
                thumb_path = os.path.join(day_folder, f"{stem}.jpg") if day_folder else ""
                json_path = os.path.join(day_folder, f"{stem}.json") if day_folder else ""

                title = stem
                description = ""
                if json_path and os.path.exists(json_path):
                    with open(json_path, "r", encoding="utf-8") as f:
                        meta = json.load(f)
                    title = meta.get("title", stem)
                    description = meta.get("description", "")

                # Convert 24h → 12h
                time_idx = idx % len(publish_times)
                raw_time = publish_times[time_idx]
                h, m = map(int, raw_time.split(":"))
                if h == 0:
                    publish_time = f"12:{m:02d} AM"
                elif h < 12:
                    publish_time = f"{h}:{m:02d} AM"
                elif h == 12:
                    publish_time = f"12:{m:02d} PM"
                else:
                    publish_time = f"{h-12}:{m:02d} PM"

                # Resolve paths
                if os.path.islink(video_path):
                    video_path = os.path.realpath(video_path)
                else:
                    video_path = os.path.abspath(video_path) if video_path else ""

                if os.path.islink(thumb_path):
                    thumb_path = os.path.realpath(thumb_path)
                else:
                    thumb_path = os.path.abspath(thumb_path) if thumb_path else ""

                if not os.path.exists(thumb_path):
                    thumb_path = ""

                # Format date: "June 1, 2026"
                parsed_date = datetime.strptime(date_str, "%Y-%m-%d")
                try:
                    publish_date_fmt = parsed_date.strftime("%B %#d, %Y")
                except ValueError:
                    publish_date_fmt = parsed_date.strftime("%B %-d, %Y")

                rows.append({
                    "profile_name": gpm_profile_name,
                    "video_path": video_path,
                    "title": title[:100],
                    "description": description[:5000],
                    "thumbnail_path": thumb_path,
                    "publish_date": publish_date_fmt,
                    "publish_time": publish_time,
                })

    if not rows:
        print(f"❌ Không có video để export")
        sys.exit(1)

    # Write Excel
    try:
        from openpyxl import Workbook
    except ImportError:
        print("❌ Cần cài openpyxl: pip install openpyxl")
        sys.exit(1)

    wb = Workbook()
    ws = wb.active
    ws.title = "Upload List"

    headers = ["profile_name", "video_path", "title", "description", "thumbnail_path", "publish_date", "publish_time"]
    ws.append(headers)

    for row in rows:
        ws.append([row[h] for h in headers])

    # Tên file tự động theo ngày nếu dùng default
    output_file = args.output
    if output_file == "upload_list.xlsx":
        if args.all:
            output_file = "upload_all.xlsx"
        else:
            date_str_file = start.strftime("%d-%m-%Y")
            output_file = f"upload_all_{date_str_file}.xlsx"

    wb.save(output_file)

    print(f"✅ Tạo file Excel: {output_file}")
    print(f"   👤 Profiles: {profiles_to_export}")
    print(f"   🎬 Videos: {len(rows)}")
    print(f"\n💡 Mở GPM Automate → set Input Excel = {output_file} → Run")


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


def cmd_gpm_profiles(args):
    """Command: Lấy danh sách profile từ GPM-Login API."""
    import json
    import os
    import requests

    # Load config
    config = {}
    if os.path.exists("config.json"):
        with open("config.json", "r", encoding="utf-8") as f:
            config = json.load(f)

    host = config.get("gpm_host", "127.0.0.1")
    port = config.get("gpm_port", 19995)
    url = f"http://{host}:{port}/api/v3/profiles"

    print(f"🔍 Đang kết nối GPM API: {url}")
    print()

    try:
        resp = requests.get(url, timeout=10)
    except requests.exceptions.ConnectionError:
        print(f"❌ Không kết nối được GPM API tại {host}:{port}")
        print(f"   → Kiểm tra GPM-Login đã mở chưa")
        print(f"   → Kiểm tra port trong config.json (gpm_port: {port})")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Lỗi: {e}")
        sys.exit(1)

    if resp.status_code != 200:
        print(f"❌ GPM API trả về status {resp.status_code}")
        sys.exit(1)

    data = resp.json()
    if not data.get("success"):
        print(f"❌ GPM API trả về lỗi: {data}")
        sys.exit(1)

    profiles = data.get("data", [])
    if not profiles:
        print("⚠️  Không có profile nào trong GPM")
        return

    # Print table
    print(f"{'#':<4} {'ID':<38} {'Name':<30} {'Proxy':<45} {'Notes'}")
    print("─" * 140)

    for i, p in enumerate(profiles, 1):
        pid = p.get("id", "")
        name = p.get("name", "")
        raw_proxy = p.get("raw_proxy", "") or ""
        notes = p.get("notes", "") or p.get("note", "") or ""
        # Truncate nếu quá dài
        if len(raw_proxy) > 43:
            raw_proxy = raw_proxy[:40] + "..."
        if len(name) > 28:
            name = name[:25] + "..."
        if len(notes) > 30:
            notes = notes[:27] + "..."
        print(f"{i:<4} {pid:<38} {name:<30} {raw_proxy:<45} {notes}")

    print("─" * 140)
    print(f"📊 Tổng: {len(profiles)} profiles")

    # Hiển thị profiles đang dùng trong config
    config_profiles = config.get("profiles", {})
    if config_profiles:
        print(f"\n📋 Profiles trong config.json:")
        for key, val in config_profiles.items():
            gpm_id = val.get("gpm_id", "")
            matched = "✅" if gpm_id in [p.get("id") for p in profiles] else "❌ (không tìm thấy)"
            print(f"   {key}: {gpm_id}  {matched}")


def cmd_info(args):
    """Command: Hiển thị thông tin tool."""
    from vtool import __version__, __app_name__
    print(f"{__app_name__} v{__version__}")
    print()
    print("Available commands:")
    print("  get-urls              Lấy danh sách URL video từ channel YouTube")
    print("  download-yt           Tải video + metadata + thumbnail từ YouTube")
    print("  get-twitch-urls       Lấy danh sách VOD URL từ channel Twitch")
    print("  download-twitch       Tải video Twitch + cắt thành từng đoạn 1 tiếng")
    print("  replace-bg            Thay nền video hàng loạt, giữ text transcript")
    print("  replace-bg-colorkey   Thay nền video bằng color key (nền đồng màu)")
    print("  replace-bg-textmask   Thay nền, giữ chữ trắng (detect text sáng)")
    print("  distribute            Chia video vào folder theo ngày cho từng kênh")
    print("  status                Xem tiến độ upload các kênh")
    print("  detect                Auto-detect vùng text trong video")
    print()
    print("Flow:")
    print("  get-urls → download-yt → replace-bg → distribute")
    print()
    print("Quick start:")
    print("  1. python run.py get-urls --channel URL")
    print("  2. python run.py download-yt --list urls.txt")
    print("  3. python run.py replace-bg")
    print("  4. python run.py distribute --profiles 'K1,K2,K3,K4,K5')")
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
    p_download.add_argument("--subtitle", action="store_true", help="Tải subtitle (.srt)")
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
    p_replace.add_argument("--overlay-opacity", type=float, default=0,
                           help="Phu den mo len text bar (0=khong, 0.5=mo 50 phan tram, 0.7=mo 70 phan tram)")
    p_replace.add_argument("--mode", default="overlay", choices=["overlay", "lumakey"],
                           help="Mode: overlay (default) hoac lumakey (giu text trang, xoa nen)")
    p_replace.add_argument("--bottom-trim", type=int, default=6,
                           help="Số pixel cắt bỏ mép dưới cùng (default: 6, tránh viền đen thừa)")
    p_replace.set_defaults(func=cmd_replace_bg)

    # === Command: download-subtitle ===
    p_dlsub = subparsers.add_parser(
        "download-subtitle",
        help="Tải subtitle (.srt) từ YouTube (không cần yt-dlp)"
    )
    p_dlsub.add_argument("--url", help="URL 1 video")
    p_dlsub.add_argument("--list", help="File chứa danh sách URL")
    p_dlsub.add_argument("--output", default="input_videos", help="Thư mục output")
    p_dlsub.add_argument("--lang", default="ja,en,vi", help="Ngôn ngữ ưu tiên (default: ja,en,vi)")
    p_dlsub.add_argument("--limit", type=int, default=None, help="Giới hạn số video")
    p_dlsub.set_defaults(func=cmd_download_subtitle)

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

    # === Command: replace-bg-textmask ===
    p_textmask = subparsers.add_parser(
        "replace-bg-textmask",
        help="Thay nền video, giữ lại chữ trắng (detect text sáng → mask → overlay lên BG mới)"
    )
    p_textmask.add_argument("--input", default="input_videos", help="Thư mục video input")
    p_textmask.add_argument("--backgrounds", default="backgrounds", help="Thư mục backgrounds")
    p_textmask.add_argument("--output", default="output_videos", help="Thư mục output")
    p_textmask.add_argument("--workers", type=int, default=2, help="Số worker (default: 2)")
    p_textmask.add_argument("--threshold", type=int, default=200,
                            help="Ngưỡng brightness giữ text 0-255 (default: 200, cao=chỉ giữ pixel rất trắng)")
    p_textmask.add_argument("--min-brightness", type=int, default=180,
                            help="Ngưỡng soft zone dưới threshold (default: 180, giữ viền text mềm)")
    p_textmask.add_argument("--softness", type=int, default=10,
                            help="Độ mượt viền (default: 10)")
    p_textmask.add_argument("--expand", type=int, default=0,
                            help="Mở rộng mask bao nhiêu pixel (default: 0, tắt để tránh lỗi filter)")
    p_textmask.add_argument("--text-region", default="full", choices=["full", "bottom"],
                            help="Vùng detect: full=toàn frame, bottom=chỉ phần dưới (default: full)")
    p_textmask.add_argument("--text-ratio", type=float, default=0.45,
                            help="Nếu --text-region=bottom, giữ bao nhiêu %% phía dưới (default: 0.45)")
    p_textmask.add_argument("--bar-opacity", type=float, default=0.6,
                            help="Độ mờ dải đen mới phía dưới (0=không có, 0.6=mờ 60%%, 1.0=đen hoàn toàn, default: 0.6)")
    p_textmask.add_argument("--bar-ratio", type=float, default=0.35,
                            help="Chiều cao dải đen + vùng text = bao nhiêu %% frame (default: 0.35 = 35%% dưới cùng)")
    p_textmask.add_argument("--crf", type=int, default=23, help="CRF 18-28 (default: 23)")
    p_textmask.add_argument("--preset", default="fast", help="FFmpeg preset (default: fast)")
    p_textmask.add_argument("--gpu", action="store_true", help="Dùng GPU")
    p_textmask.add_argument("--format", default="mp4", help="Output format")
    p_textmask.add_argument("--limit", type=int, default=None, help="Giới hạn số video")
    p_textmask.add_argument("--resolution", type=int, default=None,
                            choices=[720, 1080], help="Scale output (720/1080)")
    p_textmask.set_defaults(func=cmd_replace_bg_textmask)

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
    p_dist.add_argument("--exclusive", action="store_true",
                        help="Chia riêng - mỗi video chỉ thuộc 1 kênh (không trùng)")
    p_dist.add_argument("--shuffle", action="store_true",
                        help="Xáo trộn thứ tự video (dùng kèm --exclusive)")
    p_dist.set_defaults(func=cmd_distribute)

    # === Command: gpm-profiles ===
    p_gpm = subparsers.add_parser(
        "gpm-profiles",
        help="Lấy danh sách profile từ GPM-Login API (dạng bảng)"
    )
    p_gpm.set_defaults(func=cmd_gpm_profiles)

    # === Command: export-upload ===
    p_export = subparsers.add_parser(
        "export-upload",
        help="Tạo file Excel upload list cho GPM Automate"
    )
    p_export.add_argument("--date", default=None,
                          help="Ngày bắt đầu (2026-05-30 hoặc 30/05/2026)")
    p_export.add_argument("--days", type=int, default=1, help="Số ngày (default: 1)")
    p_export.add_argument("--all", action="store_true", help="Export tất cả ngày")
    p_export.add_argument("--profile", default=None,
                          help="Tên profile (K1, K2...) hoặc bỏ trống = tất cả kênh")
    p_export.add_argument("--schedule", default="schedules", help="Thư mục schedule")
    p_export.add_argument("--output", default="upload_list.xlsx", help="File Excel output")
    p_export.set_defaults(func=cmd_export_upload)

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
