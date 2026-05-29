# 🤖 GPM AUTOMATE - Hướng dẫn Upload YouTube

## Tổng quan

Thay vì dùng Selenium (hay lỗi), dùng GPM Automate để upload video lên YouTube.
GPM Automate ổn định hơn vì chạy trực tiếp trong browser GPM.

---

## Chuẩn bị

### 1. Tạo file Excel upload list

Chạy lệnh này để tạo file Excel từ schedule:

```powershell
python run.py export-upload --date 30/05/2026 --output upload_list.xlsx
```

File Excel sẽ có các cột:
| video_path | title | description | thumbnail_path | publish_time |
|------------|-------|-------------|----------------|--------------|
| D:\super-reup-tool\schedules\K1\day_001...\video.mp4 | Title video | Desc... | D:\...\video.jpg | 08:00 |

### 2. Mở GPM Automate

1. Mở GPM-Login → Automation → GPM Automate (Mới)
2. New Project → đặt tên "YouTube Upload"
3. Cấu hình:
   - Input Excel: chọn file `upload_list.xlsx`
   - Profile: chọn profile K1 hoặc K2

---

## Flow trong GPM Automate

### Block 1: Before browser opened
(Để trống hoặc set variables)

### Block 2: Main logic

Kéo thả các block theo thứ tự:

#### 2.1 Navigation → Go to URL
```
https://studio.youtube.com
```
Delay: 5000ms

#### 2.2 Element → Wait element
```
Selector: #create-icon
Timeout: 30000
```

#### 2.3 Mouse → Click element
```
Selector: #create-icon
```
Delay: 2000ms

#### 2.4 Mouse → Click element
```
Selector: tp-yt-paper-item:has-text("Upload videos"), tp-yt-paper-item:has-text("Tải video lên")
```
Delay: 3000ms

#### 2.5 Javascript → Execute JS code
```javascript
// Upload video file
const fileInput = document.querySelector('input[type="file"]');
if (fileInput) {
    // GPM Automate sẽ handle file upload qua biến Excel
    // Dùng inputExcelCurrentRow để lấy đường dẫn video
}
```

#### 2.6 Element → Set file input
```
Selector: input[type="file"]
Value: {{inputExcelCurrentRow.video_path}}
```
Delay: 8000ms

#### 2.7 Javascript → Execute JS code (Set Title)
```javascript
// Đợi title input xuất hiện rồi điền
async function setTitle() {
    await new Promise(r => setTimeout(r, 3000));
    
    const titleBox = document.querySelector('#textbox[aria-label*="title" i], #textbox[aria-label*="tiêu đề" i], ytcp-social-suggestions-textbox #textbox');
    if (titleBox) {
        titleBox.focus();
        document.execCommand('selectAll');
        document.execCommand('insertText', false, '{{inputExcelCurrentRow.title}}'.substring(0, 100));
    }
}
setTitle();
```
Delay: 2000ms

#### 2.8 Javascript → Execute JS code (Set Description)
```javascript
async function setDesc() {
    const descBoxes = document.querySelectorAll('#textbox[aria-label*="description" i], #textbox[aria-label*="mô tả" i]');
    if (descBoxes.length > 0) {
        const descBox = descBoxes[0];
        descBox.focus();
        descBox.click();
        await new Promise(r => setTimeout(r, 500));
        document.execCommand('selectAll');
        document.execCommand('insertText', false, '{{inputExcelCurrentRow.description}}'.substring(0, 5000));
    }
}
setDesc();
```
Delay: 2000ms

#### 2.9 Javascript → Execute JS code (Upload Thumbnail)
```javascript
// Upload thumbnail nếu có
const thumbInput = document.querySelector('input[accept="image/jpeg,image/png"]');
if (thumbInput && '{{inputExcelCurrentRow.thumbnail_path}}') {
    // GPM Automate handle file
}
```

#### 2.10 Element → Set file input (Thumbnail)
```
Selector: input[accept="image/jpeg,image/png"]
Value: {{inputExcelCurrentRow.thumbnail_path}}
```
Delay: 3000ms

#### 2.11 Javascript → Execute JS code (Set Not for Kids)
```javascript
async function setNotForKids() {
    await new Promise(r => setTimeout(r, 1000));
    const notForKids = document.querySelector('#audience [name="VIDEO_MADE_FOR_KIDS_NOT_MFK"]');
    if (notForKids) notForKids.click();
}
setNotForKids();
```
Delay: 2000ms

#### 2.12 Javascript → Execute JS code (Click Next 3 times)
```javascript
async function clickNext() {
    for (let i = 0; i < 3; i++) {
        await new Promise(r => setTimeout(r, 2000));
        const nextBtn = document.querySelector('#next-button');
        if (nextBtn) nextBtn.click();
    }
}
clickNext();
```
Delay: 8000ms

#### 2.13 Javascript → Execute JS code (Set Schedule)
```javascript
async function setSchedule() {
    // Click Schedule radio
    const scheduleRadio = document.querySelector('[name="SCHEDULE"]');
    if (scheduleRadio) {
        scheduleRadio.click();
        await new Promise(r => setTimeout(r, 2000));
    }
    
    // Set time
    const timeInput = document.querySelector('#time-of-day-trigger input, input[aria-label*="time" i]');
    if (timeInput) {
        timeInput.click();
        await new Promise(r => setTimeout(r, 500));
        timeInput.select();
        document.execCommand('insertText', false, '{{inputExcelCurrentRow.publish_time}}');
        timeInput.dispatchEvent(new Event('change', { bubbles: true }));
    }
}
setSchedule();
```
Delay: 3000ms

#### 2.14 Javascript → Execute JS code (Click Done/Publish)
```javascript
async function clickDone() {
    await new Promise(r => setTimeout(r, 2000));
    const doneBtn = document.querySelector('#done-button');
    if (doneBtn) doneBtn.click();
    
    // Đợi upload xong, đóng dialog
    await new Promise(r => setTimeout(r, 5000));
    const closeBtn = document.querySelector('#close-button, ytcp-button#close-button');
    if (closeBtn) closeBtn.click();
}
clickDone();
```
Delay: 5000ms

### Block 3: After browser closed
(Để trống)

---

## Lệnh tạo file Excel

Chạy trên PowerShell:

```powershell
# Tạo Excel cho ngày 30/05/2026, kênh K1
python run.py export-upload --date 30/05/2026 --profile K1 --output upload_K1.xlsx

# Tạo Excel cho 5 ngày, kênh K1
python run.py export-upload --date 30/05/2026 --days 5 --profile K1 --output upload_K1.xlsx

# Tạo Excel cho kênh K2
python run.py export-upload --date 30/05/2026 --profile K2 --output upload_K2.xlsx
```

---

## Cách chạy

1. Chạy `python run.py export-upload ...` → tạo file Excel
2. Mở GPM Automate → Open Project "YouTube Upload"
3. Set Input Excel = file Excel vừa tạo
4. Chọn Profile GPM
5. Bấm Run

GPM Automate sẽ loop qua từng dòng Excel, upload từng video.

---

## Lưu ý

- Mỗi lần chạy = 1 profile = 1 kênh
- Chạy K1 xong → đổi Excel + Profile → chạy K2
- Hoặc tạo 2 project riêng cho K1 và K2
- GPM Automate ổn định hơn Selenium vì chạy native trong browser
