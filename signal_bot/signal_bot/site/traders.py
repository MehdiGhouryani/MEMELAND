"""
ماژول تحلیل داده‌ها و پرونده عمومی تریدرها (Trader Dossier Engine)
"""

import logging
from typing import Any, Dict, Optional

from signal_bot.config import settings
from signal_bot.site import auth
from signal_bot.site.db import get_db

logger = logging.getLogger(__name__)


def get_trader_dossier(telegram_id: int) -> Optional[Dict[str, Any]]:
    """محاسبه و تجمیع آمار عملکرد تریدر برای نمایش در پرونده عمومی"""
    telegram_id = int(telegram_id)
    quota_info = auth.get_user_role_and_quota(telegram_id)
    profile = auth.get_profile(telegram_id)

    conn = get_db()
    try:
        c = conn.cursor()

        # استخراج نام و یوزرنیم کاربر
        username = None
        first_name = None
        c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
        if c.fetchone():
            c.execute("SELECT username, full_name FROM users WHERE user_id=?", (telegram_id,))
            user_row = c.fetchone()
            if user_row:
                username, first_name = user_row

        # آمار کل سیگنال‌ها
        c.execute(
            """
            SELECT 
                COUNT(*) as total,
                SUM(CASE WHEN outcome_status = 'win' THEN 1 ELSE 0 END) as wins,
                SUM(CASE WHEN outcome_status = 'loss' THEN 1 ELSE 0 END) as losses,
                SUM(CASE WHEN outcome_status = 'open' THEN 1 ELSE 0 END) as opens
            FROM signals 
            WHERE owner_telegram_id = ?
            """,
            (telegram_id,),
        )
        stats = c.fetchone()
        total_signals = stats[0] or 0
        wins = stats[1] or 0
        losses = stats[2] or 0
        opens = stats[3] or 0

        # محاسبه نرخ برد (Win Rate)
        closed_trades = wins + losses
        win_rate = round((wins / closed_trades * 100), 1) if closed_trades > 0 else 0.0

        # بهترین نتیجه ثبت‌شده
        c.execute(
            """
            SELECT coin, result FROM signals 
            WHERE owner_telegram_id = ? AND outcome_status = 'win' AND result IS NOT NULL 
            ORDER BY id DESC LIMIT 1
            """,
            (telegram_id,),
        )
        best_call_row = c.fetchone()
        best_call = f"{best_call_row[0]} ({best_call_row[1]})" if best_call_row else "—"

        # ۵ سیگنال اخیر این تریدر
        c.execute(
            """
            SELECT id, coin, channel, result, outcome_status, created_at 
            FROM signals 
            WHERE owner_telegram_id = ? 
            ORDER BY id DESC LIMIT 5
            """,
            (telegram_id,),
        )
        recent_signals = [
            {
                "id": r[0],
                "coin": r[1],
                "channel": r[2],
                "result": r[3],
                "outcome_status": r[4],
                "created_at": r[5],
            }
            for r in c.fetchall()
        ]

    except Exception as e:
        logger.error("Error generating dossier for %s: %s", telegram_id, e)
        return None
    finally:
        conn.close()

    display_name = profile.get("display_name") or first_name or (f"@{username}" if username else f"Trader_{telegram_id}")

    return {
        "telegram_id": telegram_id,
        "display_name": display_name,
        "username": username,
        "role_key": quota_info["role_key"],
        "display_role": quota_info["display_role"],
        "is_admin": quota_info["is_admin"],
        "total_signals": total_signals,
        "wins": wins,
        "losses": losses,
        "opens": opens,
        "win_rate": win_rate,
        "best_call": best_call,
        "recent_signals": recent_signals,
    }