"""
Module: Replace Subtitle
=========================
Tạo video mới: background + subtitle text (render lại từ file .srt).
Dùng cho video có text đè trực tiếp lên hình (không có nền riêng).
"""

from vtool.replace_subtitle.processor import batch_process_subtitle

__all__ = ["batch_process_subtitle"]
