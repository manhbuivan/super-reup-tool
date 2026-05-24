"""
VTool CLI - Entry point cho tất cả commands.

Usage:
    python -m vtool replace-bg [options]
    python -m vtool detect [video_path]
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
    print("  replace-bg   Thay nền video hàng loạt, giữ text transcript")
    print("  detect       Auto-detect vùng text trong video")
    print()
    print("Run 'python -m vtool <command> --help' for details.")


def main():
    parser = argparse.ArgumentParser(
        prog="vtool",
        description="VTool - Video Processing Toolkit"
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

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
