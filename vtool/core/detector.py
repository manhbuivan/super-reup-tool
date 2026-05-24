"""
Auto-detect text region trong video frame.

Thuật toán:
1. Lấy 1 frame từ video
2. Scan từ dưới lên, tìm vùng có nền đen/tối liên tục (text bar)
3. Detect edge giữa vùng content và text bar
4. Trả về tỷ lệ text_ratio chính xác

Hỗ trợ nhiều kiểu text bar:
- Nền đen solid
- Nền đen semi-transparent
- Nền gradient tối
"""

import os
from typing import Optional
import numpy as np

try:
    import cv2
    HAS_CV2 = True
except ImportError:
    HAS_CV2 = False


def detect_text_region(video_path: str, sample_times: list = None) -> dict:
    """
    Auto-detect vùng text bar trong video.
    
    Args:
        video_path: Đường dẫn video
        sample_times: Danh sách thời điểm lấy mẫu (giây). Default [1, 3, 5]
    
    Returns:
        dict với keys:
            - text_ratio: Tỷ lệ text bar (0.0 - 1.0)
            - text_y: Pixel y bắt đầu text bar
            - height: Chiều cao video
            - confidence: Độ tin cậy (0.0 - 1.0)
            - method: Phương pháp detect được dùng
    """
    if not HAS_CV2:
        raise ImportError(
            "OpenCV chưa được cài. Chạy: pip install opencv-python numpy"
        )
    
    if sample_times is None:
        sample_times = [1.0, 3.0, 5.0]
    
    from vtool.core.ffmpeg import extract_frame, get_video_dimensions
    
    width, height, duration, fps = get_video_dimensions(video_path)
    
    # Lấy nhiều frame để tăng độ chính xác
    valid_times = [t for t in sample_times if t < duration]
    if not valid_times:
        valid_times = [duration * 0.1, duration * 0.3, duration * 0.5]
    
    detected_positions = []
    
    for t in valid_times:
        frame_path = None
        try:
            frame_path = extract_frame(video_path, t)
            frame = cv2.imread(frame_path)
            if frame is None:
                continue
            
            position = _detect_text_bar_in_frame(frame)
            if position is not None:
                detected_positions.append(position)
        finally:
            if frame_path and os.path.exists(frame_path):
                os.remove(frame_path)
    
    if not detected_positions:
        # Fallback: dùng tỷ lệ mặc định
        return {
            "text_ratio": 0.30,
            "text_y": int(height * 0.70),
            "height": height,
            "confidence": 0.0,
            "method": "fallback_default"
        }
    
    # Lấy median position (ổn định hơn mean)
    median_y = int(np.median(detected_positions))
    text_ratio = (height - median_y) / height
    
    # Tính confidence dựa trên consistency giữa các frame
    if len(detected_positions) >= 2:
        std = np.std(detected_positions)
        confidence = max(0.0, min(1.0, 1.0 - (std / height)))
    else:
        confidence = 0.6
    
    return {
        "text_ratio": round(text_ratio, 4),
        "text_y": median_y,
        "height": height,
        "confidence": round(confidence, 3),
        "method": "edge_detection"
    }


def _detect_text_bar_in_frame(frame: np.ndarray) -> Optional[int]:
    """
    Detect vị trí bắt đầu text bar trong 1 frame.
    
    Trả về y position (pixel) nơi text bar bắt đầu, hoặc None nếu không detect được.
    """
    height, width = frame.shape[:2]
    
    # Convert sang grayscale
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    
    # === Method 1: Detect vùng tối liên tục từ dưới lên ===
    # Tính brightness trung bình theo từng hàng
    row_brightness = np.mean(gray, axis=1)
    
    # Threshold: vùng tối (text bar thường có nền đen/rất tối)
    dark_threshold = 40  # Pixel value < 40 = tối
    
    # Scan từ dưới lên tìm edge giữa vùng tối và vùng sáng
    # Chỉ scan trong 60% dưới cùng (text bar không bao giờ chiếm > 60%)
    scan_start = int(height * 0.4)
    
    # Tìm vùng tối liên tục từ dưới lên
    is_dark = row_brightness < dark_threshold
    
    # Tìm transition point: từ tối → sáng (scan từ dưới lên)
    text_bar_top = None
    consecutive_dark = 0
    min_dark_rows = int(height * 0.05)  # Ít nhất 5% height phải là dark
    
    for y in range(height - 1, scan_start, -1):
        if is_dark[y]:
            consecutive_dark += 1
        else:
            if consecutive_dark >= min_dark_rows:
                text_bar_top = y + 1
                break
            consecutive_dark = 0
    
    # Nếu toàn bộ vùng scan đều tối → text bar bắt đầu từ scan_start
    if text_bar_top is None and consecutive_dark >= min_dark_rows:
        text_bar_top = scan_start
    
    if text_bar_top is not None:
        return text_bar_top
    
    # === Method 2: Edge detection - tìm đường ngang rõ ràng ===
    # Dùng Sobel horizontal edge
    sobel_y = cv2.Sobel(gray, cv2.CV_64F, 0, 1, ksize=3)
    sobel_y = np.abs(sobel_y)
    
    # Tính edge strength theo từng hàng
    row_edge_strength = np.mean(sobel_y, axis=1)
    
    # Tìm peak edge trong vùng 40%-80% height (nơi text bar thường bắt đầu)
    search_region = row_edge_strength[scan_start:int(height * 0.85)]
    if len(search_region) == 0:
        return None
    
    # Tìm hàng có edge mạnh nhất
    peak_idx = np.argmax(search_region)
    peak_value = search_region[peak_idx]
    
    # Chỉ chấp nhận nếu edge đủ mạnh (có sự thay đổi rõ ràng)
    mean_edge = np.mean(row_edge_strength)
    if peak_value > mean_edge * 3:
        return scan_start + peak_idx
    
    return None


def detect_text_region_batch(video_paths: list) -> dict:
    """
    Detect text region cho nhiều video, trả về dict {path: result}.
    Dùng kết quả phổ biến nhất nếu các video cùng format.
    """
    results = {}
    for path in video_paths:
        try:
            results[path] = detect_text_region(path)
        except Exception as e:
            results[path] = {
                "text_ratio": 0.30,
                "text_y": 0,
                "height": 0,
                "confidence": 0.0,
                "method": f"error: {str(e)}"
            }
    return results
