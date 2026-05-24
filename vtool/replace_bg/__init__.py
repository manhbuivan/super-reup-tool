"""
Module: Replace Background
===========================
Thay nền video hàng loạt, giữ nguyên phần text transcript.
Auto-detect vùng text hoặc dùng tỷ lệ cố định.
"""

from vtool.replace_bg.processor import batch_process, process_single_video
from vtool.replace_bg.config import ReplaceBgConfig

__all__ = ["batch_process", "process_single_video", "ReplaceBgConfig"]
