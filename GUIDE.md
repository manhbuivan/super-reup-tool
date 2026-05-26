# 📖 HƯỚNG DẪN SỬ DỤNG - Super Reup Tool

## Yêu cầu hệ thống (Windows)

- Python 3.10+ (tick "Add to PATH" khi cài)
- FFmpeg (cài bằng `winget install ffmpeg`)
- GPM-Login (đã cài sẵn trên máy)
- Ổ cứng trống: ~1-3TB nếu tải 1000 video dài 1-2 tiếng

---

## Cài đặt

```powershell
git clone https://github.com/manhbuivan/super-reup-tool.git
cd super-reup-tool
pip install -r requirements.txt
```

---

## Setup config.json (làm 1 lần)

### Bước 1: Lấy GPM Profile ID

Mở GPM-Login trước, rồi chạy:

```powershell
python run.py list-profiles
```

Copy ID của từng profile.

### Bước 2: Sửa config.json

Mở file `config.json`, điền GPM ID và giờ publish cho từng kênh:

```json
{
  "profiles": {
    "K1": {
      "gpm_id": "paste-id-profile-1-vào-đây",
      "name": "Kênh 1",
      "publish_times": ["07:00", "09:00", "11:00", "13:00", "15:00", "17:00", "19:00"]
    },
    "K2": {
      "gpm_id": "paste-id-profile-2-vào-đây",
      "name": "Kênh 2",
      "publish_times": ["08:00", "10:00", "12:00", "14:00", "16:00", "18:00", "20:00"]
    },
    "K3": {
      "gpm_id": "paste-id-profile-3-vào-đây",
      "name": "Kênh 3",
      "publish_times": ["06:00", "08:30", "11:00", "13:30", "16:00", "18:30", "21:00"]
    },
    "K4": {
      "gpm_id": "paste-id-profile-4-vào-đây",
      "name": "Kênh 4",
      "publish_times": ["07:30", "09:30", "11:30", "14:00", "16:30", "19:00", "21:00"]
    },
    "K5": {
      "gpm_id": "paste-id-profile-5-vào-đây",
      "name": "Kênh 5",
      "publish_times": ["08:00", "10:30", "12:30", "14:30", "17:00", "19:30", "21:30"]
    }
  },
  "per_day": 7,
  "gap_days": 10,
  "gpm_port": 19995
}
```

---

## Flow chạy tool

### Bước 1: Lấy URL video từ channel YouTube

```powershell
python run.py get-urls --channel "https://youtube.com/@TenChannel" --limit 1000
```

Kết quả: tạo file `urls.txt` chứa 1000 URL.

---

### Bước 2: Tải video + metadata + thumbnail

```powershell
python run.py download-yt --list urls.txt
```

Hoặc giới hạn số lượng:

```powershell
python run.py download-yt --list urls.txt --limit 100
```

Hoặc tải 1 video đơn lẻ:

```powershell
python run.py download-yt --url "https://youtube.com/watch?v=xxxxx"
```

Kết quả: folder `input_videos/` chứa video + .json + .jpg

---

### Bước 3: Bỏ video/ảnh nền vào folder backgrounds

Tự copy video nền hoặc ảnh nền vào folder `backgrounds/`.
Hỗ trợ: .mp4, .mov, .avi, .mkv, .webm, .jpg, .png, .webp

**Tải video nền từ Twitch (tự cắt mỗi đoạn 1 tiếng):**

```powershell
# Lấy danh sách VOD từ channel Twitch
python run.py get-twitch-urls --channel "https://twitch.tv/username" --limit 50

# Tải + tự cắt mỗi đoạn 1 tiếng → lưu vào backgrounds/
python run.py download-twitch --list twitch_urls.txt

# Tải 1 VOD cụ thể
python run.py download-twitch --url "https://www.twitch.tv/videos/123456789"

# Cắt mỗi đoạn 30 phút
python run.py download-twitch --url "..." --split 0.5

# Cắt mỗi đoạn 2 tiếng
python run.py download-twitch --url "..." --split 2.0

# Không cắt (giữ nguyên video dài)
python run.py download-twitch --url "..." --split 999
```

Ví dụ: VOD 5 tiếng → tự cắt thành 5 file trong `backgrounds/`:
```
Stream Title_part01.mp4 (1h)
Stream Title_part02.mp4 (1h)
Stream Title_part03.mp4 (1h)
Stream Title_part04.mp4 (1h)
Stream Title_part05.mp4 (1h)
```

Lưu ý: Video Twitch dài có thể tải lâu (tuỳ mạng), tool sẽ đợi cho đến khi xong.

---

### Bước 4: Thay nền video

```powershell
python run.py replace-bg
```

Tuỳ chọn:

```powershell
# Máy yếu (ít RAM)
python run.py replace-bg --workers 2 --preset veryfast

# Chất lượng cao
python run.py replace-bg --crf 18

# Dùng GPU NVIDIA
python run.py replace-bg --gpu

# Tắt auto-detect, fix text bar 30%
python run.py replace-bg --no-detect --text-ratio 0.30
```

Kết quả: folder `output_videos/` chứa video đã thay nền + .json + .jpg

---

### Bước 5: Phân phối video cho các kênh

```powershell
python run.py distribute --profiles "K1,K2,K3,K4,K5" --per-day 7 --gap 10
```

Tuỳ chọn:

```powershell
# Chỉ 3 kênh
python run.py distribute --profiles "K1,K2,K3" --per-day 7

# Bắt đầu từ ngày cụ thể
python run.py distribute --profiles "K1,K2,K3,K4,K5" --per-day 7 --start-date 2026-06-01
```

Kết quả: folder `schedules/` chứa video chia theo ngày cho từng kênh.

---

### Bước 6: Upload lên YouTube (chạy hàng ngày)

```powershell
# Upload video cho hôm nay (7 video × 5 kênh = 35 video)
python run.py upload-gpm

# Upload trước 5 ngày (đi du lịch)
python run.py upload-gpm --days 5

# Upload public luôn (không hẹn giờ)
python run.py upload-gpm --visibility public
```

---

### Xem tiến độ

```powershell
python run.py status
```

---

## Tóm tắt tất cả lệnh

| Lệnh | Mô tả |
|-------|--------|
| `python run.py list-profiles` | Xem danh sách GPM profiles |
| `python run.py get-urls --channel URL` | Lấy URL video từ channel YouTube |
| `python run.py download-yt --list urls.txt` | Tải video YouTube + metadata + thumb |
| `python run.py get-twitch-urls --channel URL` | Lấy URL VOD từ channel Twitch |
| `python run.py download-twitch --list twitch_urls.txt` | Tải video Twitch + cắt 1h |
| `python run.py download-twitch --url URL --output backgrounds --split 999` | Tải video Twitch làm background |
| `python run.py replace-bg` | Thay nền video |
| `python run.py distribute --profiles "K1,K2,..."` | Chia video theo ngày/kênh |
| `python run.py upload-gpm` | Upload hôm nay |
| `python run.py upload-gpm --days 5` | Upload trước 5 ngày |
| `python run.py status` | Xem tiến độ các kênh |
| `python run.py detect video.mp4` | Test detect vùng text |

---

## Lưu ý quan trọng

1. **Trước khi upload**: phải mở GPM-Login trước
2. **Dung lượng**: 1000 video dài 1-2h ≈ 1-3TB, cần ổ cứng lớn
3. **Thời gian upload**: ~35-60 phút cho 35 video (5 kênh × 7 video)
4. **Video nền ngắn**: tự động loop, không cần lo
5. **Mỗi ngày chỉ cần chạy**: `python run.py upload-gpm`
6. **Đi du lịch**: chạy `python run.py upload-gpm --days 5` trước khi đi

---

## Cấu trúc folder

```
super-reup-tool/
├── config.json              ← Config GPM ID + giờ publish
├── urls.txt                 ← Danh sách URL
├── run.py                   ← Entry point
├── input_videos/            ← Video gốc tải về
├── backgrounds/             ← Video/ảnh nền
├── output_videos/           ← Video đã thay nền
└── schedules/               ← Video chia theo ngày/kênh
    ├── schedule.json
    ├── upload_log.txt       ← Log upload hàng ngày
    ├── K1/
    │   ├── day_001_2026-05-27/
    │   ├── day_002_2026-05-28/
    │   └── ...
    ├── K2/ ...
    └── K5/ ...
```
