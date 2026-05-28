"""
Module: Replace Background (Color Key)
========================================
Thay nền video bằng color key - dùng cho video LINE chat,
video có nền đồng màu (xám, đen, xanh...).
Giữ foreground (tin nhắn, topbar) overlay lên background mới.
"""

from vtool.replace_bg_colorkey.processor import batch_process_colorkey, process_single_colorkey
from vtool.replace_bg_colorkey.config import ColorKeyConfig

__all__ = ["batch_process_colorkey", "process_single_colorkey", "ColorKeyConfig"]
