"""
Module: Download Twitch
========================
Tải VOD/clip từ Twitch, tự cắt thành từng đoạn 1 tiếng nếu video dài.
"""

from vtool.download_twitch.downloader import download_twitch_videos, get_twitch_vods

__all__ = ["download_twitch_videos", "get_twitch_vods"]
