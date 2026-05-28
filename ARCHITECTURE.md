# 🏗️ KIẾN TRÚC PROJECT - Super Reup Tool

## Cấu trúc thư mục

```
super-reup-tool/
├── run.py                          ← Entry point chính
├── config.json                     ← Config GPM, Telegram, giờ publish
├── requirements.txt                ← Dependencies
├── GUIDE.md                        ← Hướng dẫn sử dụng
├── ARCHITECTURE.md                 ← File này
│
├── vtool/                          ← Package chính
│   ├── __init__.py                 ← Version, app name
│   ├── __main__.py                 ← python -m vtool
│   ├── cli.py                      ← CLI parser, tất cả commands
│   ├── notify.py                   ← Telegram notification
│   │
│   ├── core/                       ← Utilities dùng chung
│   │   ├── __init__.py
│   │   ├── ffmpeg.py               ← FFmpeg helpers (probe, extract frame, list files)
│   │   └── detector.py             ← Auto-detect text region (OpenCV)
│   │
│   ├── download_yt/                ← Module tải YouTube
│   │   ├── __init__.py
│   │   └── downloader.py           ← get_channel_urls(), download_videos()
│   │
│   ├── download_twitch/            ← Module tải Twitch
│   │   ├── __init__.py
│   │   └── downloader.py           ← get_twitch_vods(), download_twitch_videos()
│   │
│   ├── replace_bg/                 ← Module thay nền
│   │   ├── __init__.py
│   │   ├── config.py               ← ReplaceBgConfig dataclass
│   │   └── processor.py            ← process_single_video(), batch_process()
│   │
│   ├── replace_bg_colorkey/        ← Module thay nền (color key) [MỚI]
│   │   ├── __init__.py
│   │   ├── config.py               ← ColorKeyConfig dataclass
│   │   └── processor.py            ← Xử lý video LINE chat, color key
│   │
│   ├── distribute/                 ← Module phân phối video
│   │   ├── __init__.py
│   │   └── splitter.py             ← distribute_videos(), xoay vòng, append
│   │
│   └── upload_gpm/                 ← Module upload YouTube
│       ├── __init__.py
│       └── uploader.py             ← upload_daily(), GPM API, Selenium
│
├── input_videos/                   ← Video gốc tải về (gitignore)
├── output_videos/                  ← Video đã thay nền (gitignore)
├── backgrounds/                    ← Video/ảnh nền (gitignore)
└── schedules/                      ← Video chia theo ngày/kênh (gitignore)
```

---

## Modules & Responsibilities

### 1. `vtool/cli.py` — Command Router
- Parse arguments
- Route tới đúng module
- Không chứa business logic

### 2. `vtool/core/` — Shared Utilities
- `ffmpeg.py`: gọi ffprobe, extract frame, list media files
- `detector.py`: OpenCV detect text bar position

### 3. `vtool/download_yt/` — YouTube Downloader
- Dùng `yt-dlp` subprocess
- Tải video + metadata JSON + thumbnail JPG
- Ưu tiên h264+AAC format

### 4. `vtool/download_twitch/` — Twitch Downloader
- Dùng `yt-dlp` subprocess
- Tải VOD + tự cắt thành từng đoạn (FFmpeg -c copy)
- Output chỉ file .mp4 (dùng làm background)

### 5. `vtool/replace_bg/` — Replace Background (Crop + Overlay)
- Mode: crop text bar từ video gốc → overlay lên background
- Dùng cho video có text bar rõ ràng (nền đen/mờ phía dưới)
- GPU encode (NVENC), skip video đã xử lý

### 6. `vtool/replace_bg_colorkey/` — Replace Background (Color Key) [MỚI]
- Mode: dùng FFmpeg colorkey filter xoá màu nền cụ thể
- Dùng cho video LINE chat, video có nền đồng màu
- Giữ foreground (tin nhắn, topbar) → overlay lên background mới

### 7. `vtool/distribute/` — Video Distribution
- Chia video vào folder theo ngày/kênh
- Logic xoay vòng (mỗi kênh đăng tất cả video)
- Hỗ trợ append (nối thêm không ghi đè)
- Dùng symlink thay vì copy để tiết kiệm dung lượng

### 8. `vtool/upload_gpm/` — YouTube Upload via GPM-Login
- Gọi GPM API mở/đóng profile
- Connect Selenium vào browser
- Upload video + set title/desc/thumbnail
- Schedule publish (hẹn giờ)
- Hỗ trợ upload trước nhiều ngày (--days)

### 9. `vtool/notify.py` — Notifications
- Gửi Telegram khi task hoàn thành

---

## Data Flow

```
┌─────────────┐     ┌──────────────┐     ┌─────────────┐     ┌──────────────┐     ┌────────────┐
│ download-yt │     │  replace-bg  │     │ distribute  │     │  upload-gpm  │     │  YouTube   │
│ download-   │ ──► │  replace-bg  │ ──► │  (symlink)  │ ──► │  (Selenium)  │ ──► │  (publish) │
│ twitch      │     │  -colorkey   │     │             │     │              │     │            │
└─────────────┘     └──────────────┘     └─────────────┘     └──────────────┘     └────────────┘
       │                    │                    │                    │
       ▼                    ▼                    ▼                    ▼
  input_videos/       output_videos/        schedules/          upload_log.txt
  backgrounds/
```

---

## Config Schema (config.json)

```json
{
  "profiles": {
    "K1": {
      "gpm_id": "uuid-from-gpm-login",
      "name": "Tên kênh hiển thị",
      "publish_times": ["08:00", "10:00", ...]
    }
  },
  "per_day": 7,
  "gap_days": 10,
  "gpm_port": 19995,
  "telegram": {
    "bot_token": "xxx",
    "chat_id": "xxx"
  }
}
```

---

## CLI Commands

| Command | Module | Mô tả |
|---------|--------|--------|
| `get-urls` | download_yt | Lấy URL từ channel YouTube |
| `download-yt` | download_yt | Tải video YouTube |
| `get-twitch-urls` | download_twitch | Lấy URL VOD Twitch |
| `download-twitch` | download_twitch | Tải + cắt video Twitch |
| `replace-bg` | replace_bg | Thay nền (crop + overlay) |
| `replace-bg-colorkey` | replace_bg_colorkey | Thay nền (color key) [MỚI] |
| `distribute` | distribute | Chia video theo ngày/kênh |
| `upload-gpm` | upload_gpm | Upload YouTube qua GPM |
| `list-profiles` | upload_gpm | Liệt kê GPM profiles |
| `status` | cli | Xem tiến độ |
| `check` | cli | Check video lỗi |
| `detect` | core/detector | Test detect text region |

---

## Dependencies

```
opencv-python    → detect text region
numpy            → image processing
yt-dlp           → download YouTube/Twitch
selenium         → browser automation (upload)
requests         → GPM API, Telegram API
ffmpeg (system)  → video processing
```

---

## Build thành App (tương lai)

### Option 1: PyInstaller (CLI app)
```bash
pip install pyinstaller
pyinstaller --onefile run.py --name super-reup-tool
```
→ Tạo file .exe chạy trực tiếp trên Windows

### Option 2: GUI App (Electron + Python backend)
```
app/
├── frontend/          ← Electron/React UI
│   ├── src/
│   └── package.json
├── backend/           ← Python API (FastAPI)
│   ├── api.py
│   └── vtool/        ← Copy module vtool vào
└── package.json
```

### Option 3: GUI App (Python + tkinter/PyQt)
```
app/
├── gui/               ← PyQt6 UI
│   ├── main_window.py
│   ├── settings.py
│   └── progress.py
├── vtool/             ← Business logic (giữ nguyên)
└── run_gui.py         ← Entry point GUI
```

---

## Nguyên tắc code

1. **Mỗi module độc lập** — có thể import riêng lẻ
2. **CLI không chứa logic** — chỉ parse args và gọi module
3. **Config tập trung** — config.json cho tất cả settings
4. **Skip đã xử lý** — mọi bước đều check file đã tồn tại
5. **Error handling** — không crash cả batch vì 1 video lỗi
6. **Cross-platform** — chạy được Windows/Mac/Linux
