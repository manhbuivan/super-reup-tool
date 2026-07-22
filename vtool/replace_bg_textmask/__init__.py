"""
Module: Replace Background (Text Mask)
========================================
Detect chữ trắng (bright text) trong video, giữ lại text đó
và thay toàn bộ background phía sau bằng background mới.

Dùng cho: video có subtitle trắng viền đen hardcoded trên nền bất kỳ.
Kỹ thuật: threshold mask → giữ pixel sáng (text) → overlay lên BG mới.

Hỗ trợ 2 mode:
- Single background: 1 video/ảnh làm nền (mode cũ)
- Slideshow: nhiều ảnh với hiệu ứng Ken Burns (pan/zoom), chuyển cảnh mượt
"""

from vtool.replace_bg_textmask.processor import batch_process_textmask, process_single_textmask
from vtool.replace_bg_textmask.config import TextMaskConfig
from vtool.replace_bg_textmask.slideshow import generate_slideshow_video

__all__ = [
    "batch_process_textmask",
    "process_single_textmask",
    "TextMaskConfig",
    "generate_slideshow_video",
]
