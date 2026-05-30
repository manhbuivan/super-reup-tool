"""
Upload video lên YouTube qua GPM-Login API + Selenium.

Flow:
1. Đọc config.json + schedule.json
2. Xác định upload cho ngày nào (hôm nay + N ngày tới nếu --days)
3. Gọi GPM API mở profile → lấy debug port
4. Connect Selenium vào browser
5. Upload video + title + desc + thumbnail
6. Set Schedule (hẹn giờ publish đúng ngày đúng giờ)
7. Đóng profile
8. Ghi log
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


GPM_API_BASE = "http://localhost:19995"


def load_config(config_path: str = "config.json") -> dict:
    """Đọc config.json."""
    if not os.path.exists(config_path):
        return {}
    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)


def list_gpm_profiles(gpm_port: int = 19995):
    """Liệt kê tất cả GPM profiles."""
    try:
        resp = requests.get(f"http://localhost:{gpm_port}/api/v3/profiles", timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            profiles = data.get("data", [])
            print("=" * 60)
            print("👤 GPM-LOGIN PROFILES")
            print("=" * 60)
            for p in profiles:
                print(f"  ID:   {p['id']}")
                print(f"  Name: {p.get('name', 'N/A')}")
                print(f"  ---")
            print(f"\n  Tổng: {len(profiles)} profiles")
            print("=" * 60)
            print("\n💡 Copy ID vào config.json để dùng cho upload.")
            return profiles
    except Exception as e:
        print(f"❌ Không kết nối được GPM-Login: {e}")
        print("   Mở GPM-Login trước rồi thử lại.")
    return []


def upload_daily(
    schedule_dir: str = "schedules",
    config_path: str = "config.json",
    days: int = 1,
    target_date: str = None,
    visibility: str = None,
    publish_times: list = None,
    profiles_map: dict = None,
    gpm_port: int = None,
):
    """
    Upload video theo lịch.
    
    Args:
        schedule_dir: Thư mục chứa schedule.json
        config_path: Đường dẫn config.json
        days: Số ngày upload (1 = chỉ hôm nay, 5 = hôm nay + 4 ngày tới)
        visibility: public / unlisted / private / schedule
        publish_times: Danh sách giờ publish
        profiles_map: Dict mapping {profile_name: gpm_profile_id}
        gpm_port: Port GPM-Login API
    """
    global GPM_API_BASE
    
    if not HAS_SELENIUM:
        print("❌ Selenium chưa cài. Chạy: pip install selenium")
        sys.exit(1)
    
    # Load config
    config = load_config(config_path)
    
    # Merge config với arguments (arguments ưu tiên hơn)
    if gpm_port is None:
        gpm_port = config.get("gpm_port", 19995)
    GPM_API_BASE = f"http://localhost:{gpm_port}"
    
    if publish_times is None:
        publish_times = config.get("publish_times", 
                                   ["08:00", "10:00", "12:00", "14:00", "16:00", "18:00", "20:00"])
    
    if visibility is None:
        visibility = "schedule"
    
    # Build profiles map từ config nếu chưa có
    if profiles_map is None:
        profiles_map = {}
        for key, val in config.get("profiles", {}).items():
            if isinstance(val, dict):
                profiles_map[key] = val.get("gpm_id", "")
            else:
                profiles_map[key] = val
    
    # Đọc schedule
    schedule_file = os.path.join(schedule_dir, "schedule.json")
    if not os.path.exists(schedule_file):
        print(f"❌ Không tìm thấy {schedule_file}")
        print("   Chạy 'python run.py distribute' trước.")
        sys.exit(1)
    
    with open(schedule_file, "r", encoding="utf-8") as f:
        schedule_data = json.load(f)
    
    schedule = schedule_data["schedule"]
    
    # Xác định các ngày cần upload
    today = datetime.now()
    upload_dates = []
    
    if target_date:
        # Parse ngày cụ thể
        try:
            if "/" in target_date:
                # Format: 30/05/2026
                parsed = datetime.strptime(target_date, "%d/%m/%Y")
            else:
                # Format: 2026-05-30
                parsed = datetime.strptime(target_date, "%Y-%m-%d")
            upload_dates = [parsed.strftime("%Y-%m-%d")]
        except ValueError:
            print(f"❌ Format ngày sai: {target_date}")
            print("   Dùng: 2026-05-30 hoặc 30/05/2026")
            sys.exit(1)
    else:
        for i in range(days):
            d = today + timedelta(days=i)
            upload_dates.append(d.strftime("%Y-%m-%d"))
    
    print("=" * 60)
    print("🚀 UPLOAD GPM - YouTube Auto Upload + Schedule")
    print("=" * 60)
    print(f"📅 Upload cho: {upload_dates[0]} → {upload_dates[-1]} ({days} ngày)")
    print(f"👤 Profiles: {list(profiles_map.keys())}")
    print(f"🔒 Mode: {'Schedule (hẹn giờ)' if visibility == 'schedule' else visibility}")
    print(f"⏰ Giờ publish: {', '.join(publish_times)}")
    print("=" * 60)
    
    # Log file
    log_file = os.path.join(schedule_dir, "upload_log.txt")
    
    total_uploaded = 0
    total_errors = 0
    
    for profile_name, days_schedule in schedule.items():
        # Tìm GPM ID
        gpm_id = profiles_map.get(profile_name, "")
        
        if not gpm_id or gpm_id == "YOUR_GPM_PROFILE_ID_HERE":
            # Thử tìm theo tên trong GPM
            gpm_id = _find_gpm_profile_by_name(profile_name)
        
        if not gpm_id:
            print(f"\n  ❌ {profile_name}: Chưa set GPM ID trong config.json")
            continue
        
        # Lấy publish_times riêng cho profile này
        profile_times = publish_times  # default
        profile_config = config.get("profiles", {}).get(profile_name, {})
        if isinstance(profile_config, dict) and "publish_times" in profile_config:
            profile_times = profile_config["publish_times"]
        
        # Kiểm tra có video nào cần upload không
        videos_to_upload = []
        for date_str in upload_dates:
            if date_str in days_schedule:
                for video_name in days_schedule[date_str]:
                    videos_to_upload.append((date_str, video_name))
        
        if not videos_to_upload:
            print(f"\n  ⏭️  {profile_name}: Không có video cho các ngày này")
            continue
        
        print(f"\n  👤 {profile_name}: {len(videos_to_upload)} video cần upload")
        print(f"     ⏰ Giờ: {', '.join(profile_times)}")
        
        # Mở profile GPM
        driver = _open_gpm_profile(gpm_id)
        if not driver:
            print(f"     ❌ Không mở được profile GPM: {profile_name}")
            total_errors += len(videos_to_upload)
            continue
        
        try:
            for idx, (date_str, video_name) in enumerate(videos_to_upload):
                # Tìm folder chứa video
                day_folder = _find_day_folder(schedule_dir, profile_name, date_str)
                video_path = os.path.join(day_folder, video_name) if day_folder else None
                
                if not video_path or not os.path.exists(video_path):
                    print(f"     ❌ Không tìm thấy: {video_name}")
                    total_errors += 1
                    continue
                
                # Xác định giờ publish (theo index trong ngày)
                video_idx_in_day = idx % len(profile_times)
                publish_time = profile_times[video_idx_in_day]
                
                success = _upload_single_video(
                    driver, video_path, day_folder, visibility, publish_time, date_str
                )
                
                if success:
                    print(f"     ✅ {video_name} → {date_str} {publish_time}")
                    total_uploaded += 1
                else:
                    print(f"     ❌ {video_name}")
                    total_errors += 1
                
                time.sleep(5)
        
        finally:
            _close_gpm_profile(gpm_id)
            try:
                driver.quit()
            except Exception:
                pass
    
    # Ghi log
    _write_log(log_file, upload_dates, schedule, total_uploaded, total_errors, publish_times)
    
    # Summary
    print("\n" + "=" * 60)
    print(f"📊 KẾT QUẢ:")
    print(f"   ✅ Upload thành công: {total_uploaded}")
    print(f"   ❌ Lỗi: {total_errors}")
    print(f"   📅 Đã upload cho: {upload_dates[0]} → {upload_dates[-1]}")
    print(f"   📋 Log: {log_file}")
    print("=" * 60)
    
    _print_progress(schedule, upload_dates[-1])


def _find_gpm_profile_by_name(name: str) -> str:
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
            print(f"     ⚠️  Không có remote_debugging_address")
            print(f"     📋 API response: {data['data']}")
            return None
        
        print(f"     🔗 Debug port: {debug_port}")
        
        chrome_options = Options()
        chrome_options.add_experimental_option("debuggerAddress", debug_port)
        
        if browser_location:
            chrome_options.binary_location = browser_location
        
        try:
            # Thử dùng chromedriver-binary nếu có
            try:
                import chromedriver_binary
            except ImportError:
                pass
            
            from selenium.webdriver.chrome.service import Service
            driver = webdriver.Chrome(options=chrome_options)
        except Exception as e1:
            # Fallback: dùng webdriver-manager
            try:
                from selenium.webdriver.chrome.service import Service
                from webdriver_manager.chrome import ChromeDriverManager
                service = Service(ChromeDriverManager(driver_version="127.0.6533.88").install())
                driver = webdriver.Chrome(service=service, options=chrome_options)
            except Exception as e2:
                print(f"     ⚠️  ChromeDriver error: {e2}")
                print(f"     💡 Thử: pip install chromedriver-binary==127.0.6533.88.0")
                return None
        
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


def _find_day_folder(schedule_dir: str, profile_name: str, target_date: str) -> str:
    """Tìm folder chứa video cho ngày cụ thể."""
    profile_dir = os.path.join(schedule_dir, profile_name)
    
    if not os.path.exists(profile_dir):
        return None
    
    for folder in sorted(Path(profile_dir).iterdir()):
        if folder.is_dir() and target_date in folder.name:
            return str(folder)
    
    return None


def _upload_single_video(
    driver, video_path: str, day_folder: str,
    visibility: str, publish_time: str = None, publish_date: str = None
) -> bool:
    """
    Upload 1 video lên YouTube Studio.
    Dùng JavaScript để set title/desc cho ổn định.
    """
    try:
        stem = Path(video_path).stem
        
        # Đọc metadata
        json_path = os.path.join(day_folder, f"{stem}.json")
        meta = {}
        if os.path.exists(json_path):
            with open(json_path, "r", encoding="utf-8") as f:
                meta = json.load(f)
        
        title = meta.get("title", stem)[:100]
        description = meta.get("description", "")[:5000]
        
        # Thumbnail path (resolve symlink)
        thumb_path = os.path.join(day_folder, f"{stem}.jpg")
        if os.path.islink(thumb_path):
            thumb_path = os.path.realpath(thumb_path)
        thumb_path = os.path.abspath(thumb_path)
        has_thumb = os.path.exists(thumb_path)
        
        # Resolve video path (symlink)
        abs_video_path = video_path
        if os.path.islink(video_path):
            abs_video_path = os.path.realpath(video_path)
        abs_video_path = os.path.abspath(abs_video_path)
        
        # === STEP 1: Vào YouTube Studio ===
        driver.get("https://studio.youtube.com")
        time.sleep(8)
        
        wait = WebDriverWait(driver, 30)
        
        # === STEP 2: Click Create button ===
        try:
            create_btn = wait.until(EC.element_to_be_clickable(
                (By.CSS_SELECTOR, "button[aria-label='Create'], button[title='Create']")
            ))
            create_btn.click()
        except Exception:
            create_btn = driver.find_element(
                By.XPATH, "//button[@title='Create' or @aria-label='Create']"
            )
            create_btn.click()
        time.sleep(3)
        
        # === STEP 3: Click "Upload videos" ===
        try:
            upload_option = WebDriverWait(driver, 10).until(EC.element_to_be_clickable(
                (By.XPATH,
                 "//tp-yt-paper-item[contains(., 'Upload videos') or contains(., 'Tải video lên') "
                 "or contains(., '動画をアップロード')]")
            ))
            upload_option.click()
        except Exception:
            # Thử click text trực tiếp
            driver.find_element(By.XPATH, "//*[contains(text(), 'Upload video')]").click()
        time.sleep(4)
        
        # === STEP 4: Upload file ===
        file_input = wait.until(EC.presence_of_element_located(
            (By.CSS_SELECTOR, "input[type='file']")
        ))
        file_input.send_keys(abs_video_path)
        time.sleep(12)  # Đợi video upload + process
        
        # === STEP 5: Set Title bằng JavaScript ===
        # Escape title cho JS
        title_escaped = title.replace("\\", "\\\\").replace("'", "\\'").replace("\n", " ")
        driver.execute_script(f"""
            const titleBox = document.querySelector('ytcp-social-suggestions-textbox #textbox, #textbox[aria-label]');
            if (titleBox) {{
                titleBox.focus();
                titleBox.textContent = '';
                document.execCommand('selectAll');
                document.execCommand('insertText', false, '{title_escaped}');
            }}
        """)
        time.sleep(3)
        
        # === STEP 6: Set Description bằng JavaScript ===
        if description:
            desc_escaped = description.replace("\\", "\\\\").replace("'", "\\'").replace("\n", "\\n").replace("\r", "")
            driver.execute_script(f"""
                const boxes = document.querySelectorAll('#textbox[aria-label]');
                // Description thường là box thứ 2
                const descBox = boxes.length > 1 ? boxes[1] : null;
                if (descBox) {{
                    descBox.focus();
                    descBox.click();
                    document.execCommand('selectAll');
                    document.execCommand('insertText', false, '{desc_escaped}');
                }}
            """)
        time.sleep(3)
        
        # === STEP 7: Upload Thumbnail ===
        if has_thumb:
            try:
                # Tìm tất cả file input, thumbnail input thường accept image
                thumb_inputs = driver.find_elements(
                    By.CSS_SELECTOR, "input[type='file'][accept*='image'], "
                    "input[type='file'][accept*='jpeg'], "
                    "input[type='file'][accept*='png']"
                )
                if thumb_inputs:
                    thumb_inputs[0].send_keys(thumb_path)
                    time.sleep(4)
            except Exception:
                pass
        
        # === STEP 8: Set "Not made for kids" ===
        time.sleep(2)
        try:
            not_for_kids = driver.find_element(
                By.CSS_SELECTOR, "#audience [name='VIDEO_MADE_FOR_KIDS_NOT_MFK'], "
                "[name='NOT_MADE_FOR_KIDS'], #radioLabel[name='NOT_MADE_FOR_KIDS']"
            )
            not_for_kids.click()
        except Exception:
            # Thử bằng XPath
            try:
                driver.find_element(
                    By.XPATH, "//*[contains(text(), 'No, it') and contains(text(), 'not made for kids')]"
                ).click()
            except Exception:
                pass
        time.sleep(2)
        
        # === STEP 9: Click Next 3 lần ===
        for i in range(3):
            time.sleep(3)
            try:
                next_btn = wait.until(EC.element_to_be_clickable(
                    (By.CSS_SELECTOR, "#next-button")
                ))
                next_btn.click()
            except Exception:
                driver.find_element(By.XPATH, "//button[@id='next-button']").click()
        
        time.sleep(4)
        
        # === STEP 10: Set Schedule hoặc Visibility ===
        if visibility == "schedule" and publish_time and publish_date:
            _set_schedule(driver, wait, publish_date, publish_time)
        else:
            _set_visibility(driver, wait, visibility if visibility != "schedule" else "public")
        
        time.sleep(3)
        
        # === STEP 11: Click Done/Publish ===
        _wait_for_processing(driver, timeout=30)
        
        try:
            done_btn = wait.until(EC.element_to_be_clickable(
                (By.CSS_SELECTOR, "#done-button")
            ))
            done_btn.click()
        except Exception:
            driver.find_element(By.XPATH, "//button[@id='done-button']").click()
        
        time.sleep(8)
        
        # Đóng dialog nếu có
        try:
            close_btn = driver.find_element(By.CSS_SELECTOR, "#close-button")
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
    Dựa trên HTML thực tế của YouTube Studio 2026.
    """
    try:
        # === STEP 1: Click "Schedule" radio button ===
        time.sleep(2)
        try:
            # Tìm radio button có text "Schedule"
            schedule_radio = driver.find_element(
                By.XPATH, "//tp-yt-paper-radio-button[contains(., 'Schedule')]"
            )
            schedule_radio.click()
        except Exception:
            try:
                driver.find_element(By.CSS_SELECTOR, "[name='SCHEDULE']").click()
            except Exception:
                pass
        time.sleep(3)
        
        # === STEP 2: Set Date ===
        today_str = datetime.now().strftime("%Y-%m-%d")
        if publish_date != today_str:
            try:
                target_date = datetime.strptime(publish_date, "%Y-%m-%d")
                day_str = str(target_date.day)
                
                # Click vào date input để mở calendar
                date_input = driver.find_element(
                    By.CSS_SELECTOR, "#datepicker-trigger input, "
                    "ytcp-date-picker input, "
                    ".ytcp-date-picker input"
                )
                date_input.click()
                time.sleep(2)
                
                # Tìm ngày trong calendar và click
                # Calendar dùng td hoặc div chứa số ngày
                day_cells = driver.find_elements(
                    By.CSS_SELECTOR, "tp-yt-paper-calendar td button, "
                    ".tp-yt-paper-calendar td, "
                    "[class*='calendar'] td"
                )
                for cell in day_cells:
                    if cell.text.strip() == day_str:
                        cell.click()
                        break
                time.sleep(2)
            except Exception:
                # Fallback: dùng JS set date input trực tiếp
                try:
                    target_date = datetime.strptime(publish_date, "%Y-%m-%d")
                    # Format: "May 31, 2026" hoặc tương tự
                    months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                              "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
                    date_str_formatted = f"{months[target_date.month-1]} {target_date.day}, {target_date.year}"
                    driver.execute_script(f"""
                        const dateInput = document.querySelector('#datepicker-trigger input, ytcp-date-picker input');
                        if (dateInput) {{
                            dateInput.value = '{date_str_formatted}';
                            dateInput.dispatchEvent(new Event('input', {{bubbles: true}}));
                            dateInput.dispatchEvent(new Event('change', {{bubbles: true}}));
                        }}
                    """)
                    time.sleep(1)
                except Exception:
                    pass
        
        # === STEP 3: Set Time ===
        try:
            # Convert publish_time (24h format "08:00") sang 12h format ("8:00 AM")
            hour, minute = map(int, publish_time.split(":"))
            if hour == 0:
                time_12h = f"12:{minute:02d} AM"
            elif hour < 12:
                time_12h = f"{hour}:{minute:02d} AM"
            elif hour == 12:
                time_12h = f"12:{minute:02d} PM"
            else:
                time_12h = f"{hour-12}:{minute:02d} PM"
            
            # Click time dropdown trigger
            time_trigger = driver.find_element(
                By.CSS_SELECTOR, "#time-of-day-trigger, "
                "[class*='time-of-day'] [role='button'], "
                ".ytcp-time-of-day-picker [role='button']"
            )
            time_trigger.click()
            time.sleep(2)
            
            # Tìm option trong dropdown list
            time_options = driver.find_elements(
                By.CSS_SELECTOR, "tp-yt-paper-item.ytcp-time-of-day-picker, "
                "tp-yt-paper-item.style-scope.ytcp-time-of-day-picker, "
                "tp-yt-paper-listbox tp-yt-paper-item"
            )
            
            found = False
            for opt in time_options:
                opt_text = opt.text.strip()
                if opt_text == time_12h:
                    opt.click()
                    found = True
                    break
            
            # Nếu không tìm chính xác, tìm gần nhất
            if not found:
                for opt in time_options:
                    opt_text = opt.text.strip()
                    # So sánh giờ (bỏ qua phút nếu cần)
                    if f"{hour}:" in opt_text or time_12h.split(":")[0] in opt_text:
                        opt.click()
                        found = True
                        break
            
            time.sleep(2)
            
        except Exception:
            pass
    
    except Exception as e:
        print(f"     ⚠️  Schedule error: {e}, fallback to public")
        _set_visibility(driver, wait, "public")


def _set_visibility(driver, wait, visibility: str):
    """Set visibility (public/unlisted/private)."""
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
    """Đợi nút Done active."""
    try:
        WebDriverWait(driver, timeout).until(
            EC.element_to_be_clickable(
                (By.CSS_SELECTOR, "#done-button, ytcp-button#done-button")
            )
        )
    except Exception:
        pass


def _write_log(log_file: str, upload_dates: list, schedule: dict, uploaded: int, errors: int, times: list):
    """Ghi log upload."""
    now = datetime.now()
    
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(f"\n{'=' * 60}\n")
        f.write(f"📅 {now.strftime('%Y-%m-%d %H:%M:%S')} - Upload Report\n")
        f.write(f"{'=' * 60}\n")
        f.write(f"✅ Uploaded: {uploaded}\n")
        f.write(f"❌ Errors: {errors}\n")
        f.write(f"📅 Dates: {upload_dates[0]} → {upload_dates[-1]} ({len(upload_dates)} ngày)\n")
        f.write(f"⏰ Publish times: {', '.join(times)}\n")
        f.write(f"\n")
        
        f.write(f"📊 TIẾN ĐỘ CÁC KÊNH:\n")
        last_date = upload_dates[-1]
        for profile_name, days in schedule.items():
            sorted_dates = sorted(days.keys())
            if not sorted_dates:
                continue
            
            current_day_idx = sum(1 for d in sorted_dates if d <= last_date)
            total_days = len(sorted_dates)
            end_date = sorted_dates[-1]
            remaining = total_days - current_day_idx
            
            f.write(f"   👤 {profile_name}: ngày {current_day_idx}/{total_days} "
                    f"(còn {remaining} ngày, kết thúc: {end_date})\n")
        
        f.write(f"\n")


def _print_progress(schedule: dict, last_date: str):
    """In tiến độ các kênh ra console."""
    print(f"\n📊 TIẾN ĐỘ CÁC KÊNH:")
    
    for profile_name, days in schedule.items():
        sorted_dates = sorted(days.keys())
        if not sorted_dates:
            continue
        
        current_day_idx = sum(1 for d in sorted_dates if d <= last_date)
        total_days = len(sorted_dates)
        start_date = sorted_dates[0]
        end_date = sorted_dates[-1]
        remaining = total_days - current_day_idx
        
        print(f"   👤 {profile_name}:")
        print(f"      📅 Ngày {current_day_idx}/{total_days} ({start_date} → {end_date})")
        print(f"      ⏳ Còn lại: {remaining} ngày")
