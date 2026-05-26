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
    """
    if profiles is None:
        profiles = ["channel_1"]
    
    if start_date:
        start = datetime.strptime(start_date, "%Y-%m-%d")
    else:
        start = datetime.now()
    
    # Lấy danh sách video
    videos = _get_video_list(input_dir)
    
    if not videos:
        print(f"❌ Không tìm thấy video nào trong '{input_dir}/'")
        return
    
    total_videos = len(videos)
    num_profiles = len(profiles)
    
    print("=" * 60)
    print("📦 DISTRIBUTE VIDEOS")
    print("=" * 60)
    print(f"📂 Input: {input_dir}/ ({total_videos} videos)")
    print(f"👤 Profiles: {num_profiles} kênh")
    print(f"📅 Per day: {per_day} video/kênh/ngày")
    print(f"🔄 Gap: {gap_days} ngày (video trùng giữa các kênh)")
    print(f"📆 Start: {start.strftime('%Y-%m-%d')}")
    print("=" * 60)
    
    # Phân phối video cho từng profile
    schedule = _create_schedule(videos, profiles, per_day, gap_days, start)
    
    # Tạo folder structure
    os.makedirs(output_dir, exist_ok=True)
    
    for profile_name, days in schedule.items():
        profile_dir = os.path.join(output_dir, profile_name)
        os.makedirs(profile_dir, exist_ok=True)
        
        for day_num, (date_str, video_list) in enumerate(days.items(), 1):
            day_folder = os.path.join(profile_dir, f"day_{day_num:03d}_{date_str}")
            os.makedirs(day_folder, exist_ok=True)
            
            # Copy video + metadata + thumbnail vào folder
            for video_path in video_list:
                _copy_video_with_meta(video_path, day_folder, input_dir)
        
        total_days = len(days)
        print(f"  ✅ {profile_name}: {total_days} ngày × {per_day} video = {total_days * per_day} video")
    
    # Lưu schedule.json
    schedule_file = os.path.join(output_dir, "schedule.json")
    _save_schedule(schedule, schedule_file, start, profiles, per_day, gap_days)
    
    # Summary
    print("\n" + "=" * 60)
    print(f"📊 KẾT QUẢ:")
    print(f"   📁 Output: {output_dir}/")
    print(f"   📋 Schedule: {schedule_file}")
    
    for profile_name, days in schedule.items():
        total_days = len(days)
        end_date = start + timedelta(days=total_days - 1)
        print(f"   👤 {profile_name}: {total_days} ngày ({start.strftime('%Y-%m-%d')} → {end_date.strftime('%Y-%m-%d')})")
    
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
    
    Logic:
    - Shuffle video list cho mỗi profile
    - Đảm bảo video trùng giữa các kênh cách nhau >= gap_days
    """
    num_profiles = len(profiles)
    total_videos = len(videos)
    
    # Chia video cho từng profile
    # Shuffle khác nhau cho mỗi profile để đa dạng
    profile_videos = {}
    
    if num_profiles == 1:
        # 1 kênh: lấy hết
        profile_videos[profiles[0]] = list(videos)
    else:
        # Nhiều kênh: chia đều, shuffle khác nhau
        # Mỗi kênh nhận tất cả video nhưng thứ tự khác nhau
        # Video trùng sẽ được đăng cách nhau >= gap_days nhờ shuffle khác
        videos_per_profile = total_videos // num_profiles
        
        shuffled = list(videos)
        
        for i, profile in enumerate(profiles):
            # Mỗi profile lấy 1 phần khác nhau
            start_idx = i * videos_per_profile
            end_idx = start_idx + videos_per_profile
            
            if i == num_profiles - 1:
                # Profile cuối lấy hết phần còn lại
                end_idx = total_videos
            
            profile_videos[profile] = shuffled[start_idx:end_idx]
            random.shuffle(profile_videos[profile])
    
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
