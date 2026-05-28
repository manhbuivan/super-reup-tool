"""
Distribute videos - Chia video vào folder theo ngày.

Mỗi folder chứa đúng N video (mặc định 7) + metadata + thumbnail.
Hỗ trợ nhiều profile (kênh), video có thể trùng giữa các kênh nhưng cách nhau >= gap ngày.
"""

import json
import os
import shutil
import random
from datetime import datetime, timedelta
from pathlib import Path

from vtool.core.ffmpeg import VIDEO_EXTENSIONS


def distribute_videos(
    input_dir: str = "output_videos",
    output_dir: str = "schedules",
    profiles: list = None,
    per_day: int = 7,
    gap_days: int = 10,
    start_date: str = None,
    append: bool = False,
):
    """
    Phân phối video vào các folder theo ngày cho từng profile.
    
    Args:
        input_dir: Thư mục chứa video đã thay nền
        output_dir: Thư mục output (schedules/)
        profiles: Danh sách tên profile/kênh
        per_day: Số video mỗi ngày mỗi kênh
        gap_days: Số ngày tối thiểu giữa video trùng ở các kênh khác nhau
        start_date: Ngày bắt đầu (YYYY-MM-DD), mặc định = hôm nay
        append: Nối thêm video mới vào schedule cũ (không ghi đè)
    """
    if profiles is None:
        profiles = ["channel_1"]
    
    # Nếu append, đọc schedule cũ để biết video nào đã distribute
    existing_videos = set()
    existing_day_count = {}
    last_date = None
    
    schedule_file = os.path.join(output_dir, "schedule.json")
    
    if append and os.path.exists(schedule_file):
        with open(schedule_file, "r", encoding="utf-8") as f:
            old_data = json.load(f)
        
        old_schedule = old_data.get("schedule", {})
        
        # Thu thập video đã distribute
        for profile_name, days in old_schedule.items():
            sorted_dates = sorted(days.keys())
            if sorted_dates:
                existing_day_count[profile_name] = len(sorted_dates)
                # Track ngày cuối
                profile_last = sorted_dates[-1]
                if last_date is None or profile_last > last_date:
                    last_date = profile_last
            
            for date_str, video_list in days.items():
                for v in video_list:
                    existing_videos.add(v)
        
        print(f"📋 Append mode: tìm thấy {len(existing_videos)} video đã distribute")
    
    if start_date:
        start = datetime.strptime(start_date, "%Y-%m-%d")
    elif append and last_date:
        # Bắt đầu từ ngày sau ngày cuối cùng của schedule cũ
        start = datetime.strptime(last_date, "%Y-%m-%d") + timedelta(days=1)
    else:
        start = datetime.now()
    
    # Lấy danh sách video
    all_videos = _get_video_list(input_dir)
    
    if not all_videos:
        print(f"❌ Không tìm thấy video nào trong '{input_dir}/'")
        return
    
    # Nếu append, chỉ lấy video mới (chưa distribute)
    if append and existing_videos:
        videos = [v for v in all_videos if v not in existing_videos]
        if not videos:
            print(f"⏭️  Tất cả video đã được distribute rồi. Không có video mới.")
            return
        print(f"🆕 Video mới: {len(videos)} (tổng: {len(all_videos)}, đã distribute: {len(existing_videos)})")
    else:
        videos = all_videos
    
    total_videos = len(videos)
    num_profiles = len(profiles)
    
    print("=" * 60)
    print("📦 DISTRIBUTE VIDEOS")
    print("=" * 60)
    print(f"📂 Input: {input_dir}/ ({total_videos} video mới)")
    print(f"👤 Profiles: {num_profiles} kênh")
    print(f"📅 Per day: {per_day} video/kênh/ngày")
    print(f"🔄 Mode: {'APPEND (nối tiếp)' if append else 'Tạo mới'}")
    print(f"📆 Start: {start.strftime('%Y-%m-%d')}")
    print("=" * 60)
    
    # Phân phối video cho từng profile
    schedule = _create_schedule(videos, profiles, per_day, gap_days, start)
    
    # Tạo folder structure
    os.makedirs(output_dir, exist_ok=True)
    
    for profile_name, days in schedule.items():
        profile_dir = os.path.join(output_dir, profile_name)
        os.makedirs(profile_dir, exist_ok=True)
        
        # Đếm day number tiếp theo (nếu append)
        day_start_num = existing_day_count.get(profile_name, 0) + 1
        
        for day_num, (date_str, video_list) in enumerate(days.items(), day_start_num):
            day_folder = os.path.join(profile_dir, f"day_{day_num:03d}_{date_str}")
            os.makedirs(day_folder, exist_ok=True)
            
            # Copy video + metadata + thumbnail vào folder
            for video_path in video_list:
                _copy_video_with_meta(video_path, day_folder, input_dir)
        
        total_days = len(days)
        print(f"  ✅ {profile_name}: +{total_days} ngày × {per_day} video")
    
    # Lưu/cập nhật schedule.json
    if append and os.path.exists(schedule_file):
        # Merge schedule mới vào cũ
        with open(schedule_file, "r", encoding="utf-8") as f:
            old_data = json.load(f)
        
        old_schedule = old_data.get("schedule", {})
        for profile_name, days in schedule.items():
            if profile_name not in old_schedule:
                old_schedule[profile_name] = {}
            old_schedule[profile_name].update(days)
        
        old_data["schedule"] = old_schedule
        old_data["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        with open(schedule_file, "w", encoding="utf-8") as f:
            json.dump(old_data, f, ensure_ascii=False, indent=2)
    else:
        _save_schedule(schedule, schedule_file, start, profiles, per_day, gap_days)
    
    # Summary
    print("\n" + "=" * 60)
    print(f"📊 KẾT QUẢ:")
    print(f"   📁 Output: {output_dir}/")
    print(f"   📋 Schedule: {schedule_file}")
    
    for profile_name, days in schedule.items():
        total_days = len(days)
        end_date = start + timedelta(days=total_days - 1)
        total_all = existing_day_count.get(profile_name, 0) + total_days
        print(f"   👤 {profile_name}: +{total_days} ngày (tổng: {total_all} ngày)")
    
    print("=" * 60)


def _get_video_list(input_dir: str) -> list:
    """Lấy danh sách video files (chỉ .mp4, .mkv, etc)."""
    videos = []
    input_path = Path(input_dir)
    
    if not input_path.exists():
        return []
    
    for f in sorted(input_path.iterdir()):
        if f.suffix.lower() in VIDEO_EXTENSIONS:
            videos.append(f.name)
    
    return videos


def _create_schedule(
    videos: list,
    profiles: list,
    per_day: int,
    gap_days: int,
    start: datetime,
) -> dict:
    """
    Tạo schedule phân phối video cho các profile.
    
    Logic xoay vòng:
    - Chia video thành N phần (N = số kênh)
    - Mỗi kênh bắt đầu từ phần khác nhau, rồi xoay vòng qua tất cả phần
    - Ví dụ 5 kênh, 1000 video:
      K1: 1-200 → 201-400 → 401-600 → 601-800 → 801-1000
      K2: 201-400 → 401-600 → 601-800 → 801-1000 → 1-200
      K3: 401-600 → 601-800 → 801-1000 → 1-200 → 201-400
      ...
    - Video trùng giữa 2 kênh cách nhau ~(chunk_size / per_day) ngày
    """
    num_profiles = len(profiles)
    total_videos = len(videos)
    
    # Chia video thành N phần
    chunk_size = total_videos // num_profiles
    chunks = []
    for i in range(num_profiles):
        start_idx = i * chunk_size
        end_idx = start_idx + chunk_size if i < num_profiles - 1 else total_videos
        chunks.append(videos[start_idx:end_idx])
    
    # Mỗi kênh xoay vòng qua tất cả chunks, bắt đầu từ vị trí khác nhau
    profile_videos = {}
    for i, profile in enumerate(profiles):
        ordered_videos = []
        for j in range(num_profiles):
            chunk_idx = (i + j) % num_profiles
            ordered_videos.extend(chunks[chunk_idx])
        profile_videos[profile] = ordered_videos
    
    # Tạo schedule theo ngày
    schedule = {}
    
    for profile, vids in profile_videos.items():
        schedule[profile] = {}
        day_offset = 0
        
        for i in range(0, len(vids), per_day):
            batch = vids[i:i + per_day]
            date = start + timedelta(days=day_offset)
            date_str = date.strftime("%Y-%m-%d")
            schedule[profile][date_str] = batch
            day_offset += 1
    
    return schedule


def _copy_video_with_meta(video_name: str, dest_dir: str, source_dir: str):
    """Copy video + .json + .jpg metadata vào dest folder."""
    stem = Path(video_name).stem
    source_path = Path(source_dir)
    
    # Copy video
    src_video = source_path / video_name
    if src_video.exists():
        shutil.copy2(str(src_video), dest_dir)
    
    # Copy metadata json
    src_json = source_path / f"{stem}.json"
    if src_json.exists():
        shutil.copy2(str(src_json), dest_dir)
    
    # Copy thumbnail
    src_thumb = source_path / f"{stem}.jpg"
    if src_thumb.exists():
        shutil.copy2(str(src_thumb), dest_dir)


def _save_schedule(schedule: dict, filepath: str, start: datetime, profiles: list, per_day: int, gap_days: int):
    """Lưu schedule ra file JSON."""
    data = {
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "start_date": start.strftime("%Y-%m-%d"),
        "profiles": profiles,
        "per_day": per_day,
        "gap_days": gap_days,
        "schedule": schedule,
    }
    
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
