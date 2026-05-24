# VTool - Video Processing Toolkit

Bộ công cụ xử lý video hàng loạt. Modular, dễ mở rộng thêm chức năng.

## Cấu trúc project

```
new-idea/
├── run.py                       # Entry point nhanh
├── requirements.txt             # Dependencies
├── vtool/
│   ├── __init__.py              # Package info
│   ├── __main__.py              # python -m vtool
│   ├── cli.py                   # CLI router (tất cả commands)
│   ├── core/                    # Shared utilities
│   │   ├── __init__.py
│   │   ├── ffmpeg.py            # FFmpeg helpers
│   │   └── detector.py         # Auto-detect text region
│   └── replace_bg/             # Module: thay nền video
│       ├── __init__.py
│       ├── config.py
│       └── processor.py
├── input_videos/                # Video gốc
├── backgrounds/                 # Ảnh/video nền mới
└── output_videos/               # Output
```

## Setup

```bash
# Cài dependencies
pip install -r requirements.txt

# Cần FFmpeg
brew install ffmpeg
```

## Commands

### 1. Replace Background (thay nền)

```bash
# Auto-detect text region + thay nền
python run.py replace-bg

# Tùy chỉnh
python run.py replace-bg --gpu --workers 6
python run.py replace-bg --no-detect --text-ratio 0.25
python run.py replace-bg --preset ultrafast --crf 28 --workers 8
```

### 2. Detect Text Region (kiểm tra detection)

```bash
# Test detection trên 1 video
python run.py detect input_videos/sample.mp4
```

### 3. Help

```bash
python run.py --help
python run.py replace-bg --help
```

## Tham số replace-bg

| Tham số | Default | Mô tả |
|---------|---------|-------|
| `--input` | `input_videos` | Thư mục chứa video gốc |
| `--backgrounds` | `backgrounds` | Thư mục chứa background mới |
| `--output` | `output_videos` | Thư mục output |
| `--workers` | `4` | Số video xử lý song song |
| `--no-detect` | OFF | Tắt auto-detect, dùng ratio cố định |
| `--text-ratio` | `0.30` | Fallback ratio nếu detect thất bại |
| `--preset` | `fast` | FFmpeg preset (ultrafast → medium) |
| `--crf` | `23` | Chất lượng (18=cao, 28=thấp) |
| `--gpu` | OFF | Bật GPU acceleration (Mac) |
| `--format` | `mp4` | Format output |

## Auto-detect hoạt động thế nào

1. Trích xuất vài frame từ video (tại 1s, 3s, 5s)
2. Phân tích brightness theo từng hàng pixel
3. Tìm vùng tối liên tục từ dưới lên (text bar = nền đen)
4. Nếu không tìm được → dùng Sobel edge detection tìm đường phân cách
5. Lấy median từ nhiều frame → kết quả ổn định
6. Nếu confidence thấp → fallback về `--text-ratio`

## Thêm module mới

Để thêm chức năng mới (ví dụ: add_subtitle, split_scenes):

```
vtool/
├── new_module/
│   ├── __init__.py
│   ├── config.py
│   └── processor.py
```

Rồi thêm command vào `vtool/cli.py`:

```python
# Trong cli.py, thêm subparser mới
p_new = subparsers.add_parser("new-command", help="Mô tả")
p_new.add_argument(...)
p_new.set_defaults(func=cmd_new_function)
```

## Tips tối ưu throughput

```bash
# Mac M1/M2/M3 - GPU + parallel
python run.py replace-bg --gpu --workers 6 --preset fast

# Ưu tiên tốc độ
python run.py replace-bg --workers 8 --preset ultrafast --crf 28

# Ưu tiên chất lượng
python run.py replace-bg --workers 4 --preset medium --crf 20
```
