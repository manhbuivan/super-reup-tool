"""
Upload video lên YouTube qua GPM-Login API + Selenium.

Flow:
1. Đọc schedule.json → xác định hôm nay upload video nào cho kênh nào
2. Gọi GPM API mở profile → lấy debug port
3. Connect Selenium vào browser
4. Vào YouTube Studio → Upload video + title + desc + thumbnail
5. Set Schedule (hẹn giờ publish)
6. Đóng profile
7. Ghi log
"""

import json
import os
import sys
import time
from datetime import datetime, timedelta
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


def upload_daily(
    schedule_dir: str = "schedules",
    profiles_map: dict = None,
    visibility: str = "schedule",
    publish_times: list = None,
    gpm_port: int = 19995,
):
    """
    Upload video theo lịch hôm nay.
    
    Args:
        schedule_dir: Thư mục chứa schedule.json
        profiles_map: Dict mapping {profile_name: gpm_profile_id}
        visibility: public / unlisted / private / schedule
        publish_times: Danh sách giờ publish (vd: ["08:00","10:00","12:00",...])
        gpm_port: Port GPM-Login API
    """
    global GPM_API_BASE
    GPM_API_BASE = f"http://localhost:{gpm_port}"
    
    if not HAS_SELENIUM:
        print("❌ Selenium chưa cài. Chạy: pip install selenium")
        sys.exit(1)
    
    # Default publish times: 7 khung giờ trong ngày
    if publish_times is None:
        publish_times = ["08:00", "10:00", "12:00", "14:00", "16:00", "18:00", "20:00"]
    
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
    print("🚀 UPLOAD GPM - YouTube Auto Upload + Schedule")
    print("=" * 60)
    print(f"📅 Hôm nay: {today}")
    print(f"👤 Profiles: {list(schedule.keys())}")
    print(f"🔒 Mode: {'Schedule (hẹn giờ)' if visibility == 'schedule' else visibility}")
    if visibility == "schedule":
        print(f"⏰ Giờ publish: {', '.join(publish_times)}")
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
            # Tìm folder chứa video hôm nay
            day_folder = _find_day_folder(schedule_dir, profile_name, today)
            
            for idx, video_name in enumerate(videos_today):
                video_path = os.path.join(day_folder, video_name) if day_folder else None
                
                if not video_path or not os.path.exists(video_path):
                    print(f"     ❌ Không tìm thấy: {video_name}")
                    total_errors += 1
                    continue
                
                # Xác định giờ publish cho video này
                publish_time = None
                if visibility == "schedule":
                    time_idx = idx % len(publish_times)
                    publish_time = publish_times[time_idx]
                
                success = _upload_single_video(
                    driver, video_path, day_folder, visibility, publish_time, today
                )
                
                if success:
                    time_info = f" → hẹn {publish_time}" if publish_time else ""
                    print(f"     ✅ {video_name}{time_info}")
                    total_uploaded += 1
                else:
                    print(f"     ❌ {video_name}")
                    total_errors += 1
                
                # Delay giữa các video
                time.sleep(5)
        
        finally:
            _close_gpm_profile(gpm_id)
            try:
                driver.quit()
            except Exception:
                pass
    
    # Ghi log
    _write_log(log_file, today, schedule, total_uploaded, total_errors, publish_times)
    
    # Summary
    print("\n" + "=" * 60)
    print(f"📊 KẾT QUẢ HÔM NAY ({today}):")
    print(f"   ✅ Upload thành công: {total_uploaded}")
    print(f"   ❌ Lỗi: {total_errors}")
    print(f"   📋 Log: {log_file}")
    print("=" * 60)
    
    _print_progress(schedule, today)


def _find_gpm_profile(name: str) -> str:
    """Tìm GPM profile ID theo tên."""
    try:
        resp = requests.get(f"{GPM_API_BASE}/api/v3/profiles", timeout=5)
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
        start_url = f"{GPM_API_BASE}/api/v3/profiles/start/{profile_id}"
        resp = requests.get(start_url, timeout=30)
        
        if resp.status_code != 200:
            return None
        
        data = resp.json()
        if not data.get("success"):
            return None
        
        debug_port = data["data"].get("remote_debugging_address", "")
        browser_location = data["data"].get("browser_location", "")
        
        if not debug_port:
            return None
        
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
    
    for folder in sorted(Path(profile_dir).iterdir()):
        if folder.is_dir() and today in folder.name:
            return str(folder)
    
    return None


def _upload_single_video(
    driver, video_path: str, day_folder: str,
    visibility: str, publish_time: str = None, publish_date: str = None
) -> bool:
    """
    Upload 1 video lên YouTube Studio.
    Nếu visibility == "schedule": set hẹn giờ publish.
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
        time.sleep(4)
        
        wait = WebDriverWait(driver, 30)
        
        # Click Create button
        create_btn = wait.until(EC.element_to_be_clickable(
            (By.CSS_SELECTOR, "#create-icon, ytcp-button#create-icon, [id='create-icon']")
        ))
        create_btn.click()
        time.sleep(2)
        
        # Click "Upload videos"
        upload_option = wait.until(EC.element_to_be_clickable(
            (By.XPATH, 
             "//tp-yt-paper-item[contains(., 'Upload videos') or contains(., 'Tải video lên')]")
        ))
        upload_option.click()
        time.sleep(3)
        
        # Upload file
        file_input = driver.find_element(By.CSS_SELECTOR, "input[type='file']")
        file_input.send_keys(os.path.abspath(video_path))
        time.sleep(8)
        
        # Điền title
        title_input = wait.until(EC.presence_of_element_located(
            (By.CSS_SELECTOR,
             "#textbox[aria-label*='title' i], "
             "#textbox[aria-label*='tiêu đề' i], "
             "ytcp-social-suggestions-textbox #textbox")
        ))
        title_input.clear()
        title_input.send_keys(Keys.CONTROL + "a")
        time.sleep(0.5)
        title_input.send_keys(title[:100])
        time.sleep(1)
        
        # Điền description
        desc_inputs = driver.find_elements(
            By.CSS_SELECTOR,
            "#textbox[aria-label*='description' i], "
            "#textbox[aria-label*='mô tả' i]"
        )
        if desc_inputs and description:
            desc_inputs[0].click()
            time.sleep(0.5)
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
                pass
        
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
        
        # === SET VISIBILITY / SCHEDULE ===
        if visibility == "schedule" and publish_time:
            _set_schedule(driver, wait, publish_date, publish_time)
        else:
            _set_visibility(driver, wait, visibility)
        
        time.sleep(2)
        
        # Đợi video xử lý xong (check progress)
        _wait_for_processing(driver, timeout=60)
        
        # Click Publish/Schedule/Save
        done_btn = wait.until(EC.element_to_be_clickable(
            (By.CSS_SELECTOR, "#done-button, ytcp-button#done-button")
        ))
        done_btn.click()
        time.sleep(5)
        
        # Đóng dialog nếu có
        try:
            close_btn = driver.find_element(
                By.CSS_SELECTOR, "#close-button, ytcp-button#close-button"
            )
            close_btn.click()
        except Exception:
            pass
        
        time.sleep(3)
        return True
        
    except Exception as e:
        print(f"     ⚠️  Upload error: {e}")
        return False


def _set_schedule(driver, wait, publish_date: str, publish_time: str):
    """
    Set schedule (hẹn giờ publish) cho video.
    
    YouTube Studio flow:
    1. Click radio "Schedule"
    2. Set date
    3. Set time
    """
    try:
        # Click "Schedule" radio button
        schedule_radio = wait.until(EC.element_to_be_clickable(
            (By.CSS_SELECTOR, "[name='SCHEDULE'], #schedule-radio-button")
        ))
        schedule_radio.click()
        time.sleep(2)
        
        # Set date - click vào date picker
        # YouTube mặc định ngày mai, ta cần set đúng ngày
        try:
            date_picker = driver.find_element(
                By.CSS_SELECTOR, "#datepicker-trigger, ytcp-date-picker"
            )
            date_picker.click()
            time.sleep(1)
            
            # Parse ngày cần set
            target_date = datetime.strptime(publish_date, "%Y-%m-%d")
            day_str = str(target_date.day)
            
            # Tìm và click ngày trong calendar
            # YouTube calendar hiển thị ngày hiện tại, ta click ngày target
            day_buttons = driver.find_elements(
                By.CSS_SELECTOR, ".tp-yt-paper-calendar-day, .calendar-day"
            )
            for btn in day_buttons:
                if btn.text.strip() == day_str:
                    btn.click()
                    break
            time.sleep(1)
        except Exception:
            pass  # Giữ ngày mặc định (hôm nay hoặc ngày mai)
        
        # Set time
        try:
            time_input = driver.find_element(
                By.CSS_SELECTOR, 
                "#time-of-day-trigger input, "
                "ytcp-form-input-container input[aria-label*='time' i], "
                "ytcp-form-input-container input[aria-label*='giờ' i], "
                "#time-of-day-container input"
            )
            time_input.click()
            time.sleep(0.5)
            time_input.send_keys(Keys.CONTROL + "a")
            time_input.send_keys(publish_time)
            time_input.send_keys(Keys.TAB)
            time.sleep(1)
        except Exception:
            # Fallback: tìm dropdown time
            try:
                time_dropdown = driver.find_element(
                    By.CSS_SELECTOR, "#time-of-day-trigger"
                )
                time_dropdown.click()
                time.sleep(1)
                
                # Tìm option gần nhất với publish_time
                time_options = driver.find_elements(
                    By.CSS_SELECTOR, 
                    "tp-yt-paper-item, ytcp-text-dropdown-trigger-option"
                )
                for option in time_options:
                    if publish_time in option.text:
                        option.click()
                        break
                time.sleep(1)
            except Exception:
                pass
    
    except Exception as e:
        print(f"     ⚠️  Schedule error: {e}, fallback to public")
        _set_visibility(driver, wait, "public")


def _set_visibility(driver, wait, visibility: str):
    """Set visibility cho video (public/unlisted/private)."""
    try:
        if visibility == "public":
            radio = driver.find_element(By.CSS_SELECTOR, "[name='PUBLIC']")
        elif visibility == "unlisted":
            radio = driver.find_element(By.CSS_SELECTOR, "[name='UNLISTED']")
        else:
            radio = driver.find_element(By.CSS_SELECTOR, "[name='PRIVATE']")
        radio.click()
    except Exception:
        try:
            labels = driver.find_elements(
                By.CSS_SELECTOR, "#privacy-radios tp-yt-paper-radio-button"
            )
            for label in labels:
                if visibility.lower() in label.text.lower():
                    label.click()
                    break
        except Exception:
            pass


def _wait_for_processing(driver, timeout: int = 60):
    """Đợi YouTube xử lý video (không bắt buộc phải xong 100%)."""
    try:
        # Đợi tối đa timeout giây cho nút Done/Schedule active
        WebDriverWait(driver, timeout).until(
            EC.element_to_be_clickable(
                (By.CSS_SELECTOR, "#done-button, ytcp-button#done-button")
            )
        )
    except Exception:
        pass  # Timeout thì cứ bấm Done


def _write_log(log_file: str, today: str, schedule: dict, uploaded: int, errors: int, times: list):
    """Ghi log upload."""
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(f"\n{'=' * 60}\n")
        f.write(f"📅 {today} - Upload Report\n")
        f.write(f"{'=' * 60}\n")
        f.write(f"✅ Uploaded: {uploaded}\n")
        f.write(f"❌ Errors: {errors}\n")
        f.write(f"⏰ Publish times: {', '.join(times)}\n")
        f.write(f"🕐 Run at: {datetime.now().strftime('%H:%M:%S')}\n")
        f.write(f"\n")
        
        f.write(f"📊 TIẾN ĐỘ CÁC KÊNH:\n")
        for profile_name, days in schedule.items():
            sorted_dates = sorted(days.keys())
            if not sorted_dates:
                continue
            
            current_day_idx = 0
            for i, d in enumerate(sorted_dates):
                if d <= today:
                    current_day_idx = i + 1
            
            total_days = len(sorted_dates)
            end_date = sorted_dates[-1] if sorted_dates else "N/A"
            remaining = total_days - current_day_idx
            
            f.write(f"   👤 {profile_name}: ngày {current_day_idx}/{total_days} "
                    f"(còn {remaining} ngày, kết thúc: {end_date})\n")
        
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
