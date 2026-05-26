"""
Upload video lên YouTube qua GPM-Login API + Selenium.

Flow:
1. Đọc schedule.json → xác định hôm nay upload video nào cho kênh nào
2. Gọi GPM API mở profile → lấy debug port
3. Connect Selenium vào browser
4. Vào YouTube Studio → Upload video + title + desc + thumbnail
5. Đóng profile
6. Ghi log
"""

import json
import os
import sys
import time
import logging
from datetime import datetime
from pathlib import Path

import requests

try:
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.common.keys import Keys
    HAS_SELENIUM = True
except ImportError:
    HAS_SELENIUM = False


# GPM-Login API
GPM_API_BASE = "http://localhost:19995"
GPM_API_PROFILES = f"{GPM_API_BASE}/api/v3/profiles"


def upload_daily(
    schedule_dir: str = "schedules",
    profiles_map: dict = None,
    visibility: str = "public",
    gpm_port: int = 19995,
):
    """
    Upload video theo lịch hôm nay.
    
    Args:
        schedule_dir: Thư mục chứa schedule.json
        profiles_map: Dict mapping {profile_name: gpm_profile_id}
        visibility: public / unlisted / private
        gpm_port: Port GPM-Login API
    """
    global GPM_API_BASE, GPM_API_PROFILES
    GPM_API_BASE = f"http://localhost:{gpm_port}"
    GPM_API_PROFILES = f"{GPM_API_BASE}/api/v3/profiles"
    
    if not HAS_SELENIUM:
        print("❌ Selenium chưa cài. Chạy: pip install selenium")
        sys.exit(1)
    
    # Đọc schedule
    schedule_file = os.path.join(schedule_dir, "schedule.json")
    if not os.path.exists(schedule_file):
        print(f"❌ Không tìm thấy {schedule_file}")
        print("   Chạy 'python run.py distribute' trước.")
        sys.exit(1)
    
    with open(schedule_file, "r", encoding="utf-8") as f:
        schedule_data = json.load(f)
    
    today = datetime.now().strftime("%Y-%m-%d")
    schedule = schedule_data["schedule"]
    
    print("=" * 60)
    print("🚀 UPLOAD GPM - YouTube Auto Upload")
    print("=" * 60)
    print(f"📅 Hôm nay: {today}")
    print(f"👤 Profiles: {list(schedule.keys())}")
    print(f"🔒 Visibility: {visibility}")
    print("=" * 60)
    
    # Log file
    log_file = os.path.join(schedule_dir, "upload_log.txt")
    
    total_uploaded = 0
    total_errors = 0
    
    for profile_name, days in schedule.items():
        if today not in days:
            print(f"\n  ⏭️  {profile_name}: Không có video cho hôm nay")
            continue
        
        videos_today = days[today]
        print(f"\n  👤 {profile_name}: {len(videos_today)} video cần upload")
        
        # Tìm GPM profile ID
        gpm_id = None
        if profiles_map and profile_name in profiles_map:
            gpm_id = profiles_map[profile_name]
        else:
            # Tìm theo tên
            gpm_id = _find_gpm_profile(profile_name)
        
        if not gpm_id:
            print(f"     ❌ Không tìm thấy GPM profile: {profile_name}")
            total_errors += len(videos_today)
            continue
        
        # Mở profile GPM
        driver = _open_gpm_profile(gpm_id)
        if not driver:
            print(f"     ❌ Không mở được profile GPM: {profile_name}")
            total_errors += len(videos_today)
            continue
        
        try:
            # Upload từng video
            # Tìm folder chứa video hôm nay
            day_folder = _find_day_folder(schedule_dir, profile_name, today)
            
            for video_name in videos_today:
                video_path = os.path.join(day_folder, video_name) if day_folder else None
                
                if not video_path or not os.path.exists(video_path):
                    print(f"     ❌ Không tìm thấy: {video_name}")
                    total_errors += 1
                    continue
                
                success = _upload_single_video(driver, video_path, day_folder, visibility)
                
                if success:
                    print(f"     ✅ {video_name}")
                    total_uploaded += 1
                else:
                    print(f"     ❌ {video_name}")
                    total_errors += 1
                
                # Delay giữa các video
                time.sleep(5)
        
        finally:
            # Đóng profile
            _close_gpm_profile(gpm_id)
            try:
                driver.quit()
            except Exception:
                pass
    
    # Ghi log
    _write_log(log_file, today, schedule, total_uploaded, total_errors)
    
    # Summary
    print("\n" + "=" * 60)
    print(f"📊 KẾT QUẢ HÔM NAY ({today}):")
    print(f"   ✅ Upload thành công: {total_uploaded}")
    print(f"   ❌ Lỗi: {total_errors}")
    print(f"   📋 Log: {log_file}")
    print("=" * 60)
    
    # Hiển thị tiến độ các kênh
    _print_progress(schedule, today)


def _find_gpm_profile(name: str) -> str:
    """Tìm GPM profile ID theo tên."""
    try:
        resp = requests.get(GPM_API_PROFILES, timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            for profile in data.get("data", []):
                if profile.get("name", "").lower() == name.lower():
                    return profile["id"]
                if profile.get("id") == name:
                    return name
    except Exception:
        pass
    return None


def _open_gpm_profile(profile_id: str) -> object:
    """Mở GPM profile và connect Selenium."""
    try:
        # Gọi API mở profile
        start_url = f"{GPM_API_BASE}/api/v3/profiles/start/{profile_id}"
        resp = requests.get(start_url, timeout=30)
        
        if resp.status_code != 200:
            return None
        
        data = resp.json()
        if not data.get("success"):
            return None
        
        # Lấy debug port
        debug_port = data["data"].get("remote_debugging_address", "")
        browser_location = data["data"].get("browser_location", "")
        
        if not debug_port:
            return None
        
        # Connect Selenium
        chrome_options = Options()
        chrome_options.add_experimental_option("debuggerAddress", debug_port)
        
        if browser_location:
            chrome_options.binary_location = browser_location
        
        driver = webdriver.Chrome(options=chrome_options)
        return driver
        
    except Exception as e:
        print(f"     ⚠️  Lỗi mở profile: {e}")
        return None


def _close_gpm_profile(profile_id: str):
    """Đóng GPM profile."""
    try:
        close_url = f"{GPM_API_BASE}/api/v3/profiles/close/{profile_id}"
        requests.get(close_url, timeout=10)
    except Exception:
        pass


def _find_day_folder(schedule_dir: str, profile_name: str, today: str) -> str:
    """Tìm folder chứa video cho ngày hôm nay."""
    profile_dir = os.path.join(schedule_dir, profile_name)
    
    if not os.path.exists(profile_dir):
        return None
    
    # Tìm folder có chứa ngày hôm nay trong tên
    for folder in sorted(Path(profile_dir).iterdir()):
        if folder.is_dir() and today in folder.name:
            return str(folder)
    
    return None


def _upload_single_video(driver, video_path: str, day_folder: str, visibility: str) -> bool:
    """
    Upload 1 video lên YouTube Studio.
    
    Returns:
        True nếu thành công
    """
    try:
        stem = Path(video_path).stem
        
        # Đọc metadata
        json_path = os.path.join(day_folder, f"{stem}.json")
        meta = {}
        if os.path.exists(json_path):
            with open(json_path, "r", encoding="utf-8") as f:
                meta = json.load(f)
        
        title = meta.get("title", stem)
        description = meta.get("description", "")
        
        # Thumbnail path
        thumb_path = os.path.join(day_folder, f"{stem}.jpg")
        has_thumb = os.path.exists(thumb_path)
        
        # Vào YouTube Studio
        driver.get("https://studio.youtube.com")
        time.sleep(3)
        
        # Click nút Upload (Create button)
        wait = WebDriverWait(driver, 20)
        
        # Click Create button
        create_btn = wait.until(EC.element_to_be_clickable(
            (By.CSS_SELECTOR, "#create-icon, ytcp-button#create-icon, [id='create-icon']")
        ))
        create_btn.click()
        time.sleep(1)
        
        # Click "Upload videos"
        upload_option = wait.until(EC.element_to_be_clickable(
            (By.XPATH, "//tp-yt-paper-item[contains(., 'Upload videos') or contains(., 'Tải video lên')]")
        ))
        upload_option.click()
        time.sleep(2)
        
        # Upload file
        file_input = driver.find_element(By.CSS_SELECTOR, "input[type='file']")
        file_input.send_keys(os.path.abspath(video_path))
        time.sleep(5)
        
        # Điền title
        title_input = wait.until(EC.presence_of_element_located(
            (By.CSS_SELECTOR, "#textbox[aria-label*='title' i], #textbox[aria-label*='tiêu đề' i], "
             "ytcp-social-suggestions-textbox #textbox")
        ))
        title_input.clear()
        title_input.send_keys(Keys.CONTROL + "a")
        title_input.send_keys(title[:100])  # YouTube giới hạn 100 ký tự
        time.sleep(1)
        
        # Điền description
        desc_inputs = driver.find_elements(
            By.CSS_SELECTOR, "#textbox[aria-label*='description' i], #textbox[aria-label*='mô tả' i]"
        )
        if desc_inputs and description:
            desc_inputs[0].click()
            desc_inputs[0].send_keys(Keys.CONTROL + "a")
            desc_inputs[0].send_keys(description[:5000])
            time.sleep(1)
        
        # Upload thumbnail
        if has_thumb:
            try:
                thumb_input = driver.find_element(
                    By.CSS_SELECTOR, "input[accept='image/jpeg,image/png']"
                )
                thumb_input.send_keys(os.path.abspath(thumb_path))
                time.sleep(3)
            except Exception:
                pass  # Thumbnail optional
        
        # Set "Not made for kids"
        try:
            not_for_kids = driver.find_element(
                By.CSS_SELECTOR, "#audience [name='VIDEO_MADE_FOR_KIDS_NOT_MFK']"
            )
            not_for_kids.click()
            time.sleep(1)
        except Exception:
            pass
        
        # Click Next 3 lần (Details → Video elements → Checks → Visibility)
        for _ in range(3):
            next_btn = wait.until(EC.element_to_be_clickable(
                (By.CSS_SELECTOR, "#next-button, ytcp-button#next-button")
            ))
            next_btn.click()
            time.sleep(2)
        
        # Set visibility
        _set_visibility(driver, wait, visibility)
        time.sleep(1)
        
        # Click Publish/Save
        publish_btn = wait.until(EC.element_to_be_clickable(
            (By.CSS_SELECTOR, "#done-button, ytcp-button#done-button")
        ))
        publish_btn.click()
        time.sleep(5)
        
        # Đóng dialog nếu có
        try:
            close_btn = driver.find_element(By.CSS_SELECTOR, "#close-button, ytcp-button#close-button")
            close_btn.click()
        except Exception:
            pass
        
        time.sleep(2)
        return True
        
    except Exception as e:
        print(f"     ⚠️  Upload error: {e}")
        return False


def _set_visibility(driver, wait, visibility: str):
    """Set visibility cho video."""
    try:
        if visibility == "public":
            radio = driver.find_element(By.CSS_SELECTOR, "[name='PUBLIC']")
        elif visibility == "unlisted":
            radio = driver.find_element(By.CSS_SELECTOR, "[name='UNLISTED']")
        else:
            radio = driver.find_element(By.CSS_SELECTOR, "[name='PRIVATE']")
        radio.click()
    except Exception:
        # Fallback: tìm theo text
        try:
            labels = driver.find_elements(By.CSS_SELECTOR, "#privacy-radios tp-yt-paper-radio-button")
            for label in labels:
                if visibility.lower() in label.text.lower():
                    label.click()
                    break
        except Exception:
            pass


def _write_log(log_file: str, today: str, schedule: dict, uploaded: int, errors: int):
    """Ghi log upload."""
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(f"\n{'=' * 60}\n")
        f.write(f"📅 {today} - Upload Report\n")
        f.write(f"{'=' * 60}\n")
        f.write(f"✅ Uploaded: {uploaded}\n")
        f.write(f"❌ Errors: {errors}\n")
        f.write(f"⏰ Time: {datetime.now().strftime('%H:%M:%S')}\n")
        f.write(f"\n")
        
        # Tiến độ từng kênh
        f.write(f"📊 TIẾN ĐỘ CÁC KÊNH:\n")
        for profile_name, days in schedule.items():
            sorted_dates = sorted(days.keys())
            if not sorted_dates:
                continue
            
            # Tìm ngày hiện tại trong schedule
            current_day_idx = 0
            for i, d in enumerate(sorted_dates):
                if d <= today:
                    current_day_idx = i + 1
            
            total_days = len(sorted_dates)
            end_date = sorted_dates[-1] if sorted_dates else "N/A"
            
            f.write(f"   👤 {profile_name}: ngày {current_day_idx}/{total_days} "
                    f"(kết thúc: {end_date})\n")
        
        f.write(f"\n")


def _print_progress(schedule: dict, today: str):
    """In tiến độ các kênh ra console."""
    print(f"\n📊 TIẾN ĐỘ CÁC KÊNH:")
    
    for profile_name, days in schedule.items():
        sorted_dates = sorted(days.keys())
        if not sorted_dates:
            continue
        
        current_day_idx = 0
        for i, d in enumerate(sorted_dates):
            if d <= today:
                current_day_idx = i + 1
        
        total_days = len(sorted_dates)
        start_date = sorted_dates[0]
        end_date = sorted_dates[-1]
        remaining = total_days - current_day_idx
        
        print(f"   👤 {profile_name}:")
        print(f"      📅 Ngày {current_day_idx}/{total_days} ({start_date} → {end_date})")
        print(f"      ⏳ Còn lại: {remaining} ngày")
