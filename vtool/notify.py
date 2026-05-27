"""
Telegram notification - Gửi thông báo khi task hoàn thành.
"""

import requests


def send_telegram(message: str, bot_token: str, chat_id: str) -> bool:
    """
    Gửi tin nhắn qua Telegram Bot.
    
    Args:
        message: Nội dung tin nhắn
        bot_token: Token bot Telegram
        chat_id: Chat ID nhận tin nhắn
    
    Returns:
        True nếu gửi thành công
    """
    if not bot_token or not chat_id:
        return False
    
    try:
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        data = {
            "chat_id": chat_id,
            "text": message,
            "parse_mode": "HTML",
        }
        resp = requests.post(url, data=data, timeout=10)
        return resp.status_code == 200
    except Exception:
        return False
