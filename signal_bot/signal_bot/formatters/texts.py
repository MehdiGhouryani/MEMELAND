"""
ساخت متن‌های HTML نمایشی برای پیام‌های ربات.
این توابع فقط از db repo ها داده می‌خونن و رشته می‌سازن — هیچ SQL خامی اینجا نیست.
"""
from datetime import datetime, timedelta

from signal_bot.config.settings import SEP, SEP2, LEVELS, RESULT_LABEL, SIGNAL_TYPE_LABELS
from signal_bot.db import signals_repo, prize_repo, users_repo, rewards_repo
from signal_bot.services import access, alpha_score
from signal_bot.utils import esc


def progress_bar(pts):
    next_level_pts = None
    for threshold, name in LEVELS:
        if pts < threshold:
            next_level_pts = threshold
            break
    if not next_level_pts:
        return "MAX LEVEL 🔱"
    prev = 0
    for threshold, name in LEVELS:
        if pts >= threshold:
            prev = threshold
    progress = pts - prev
    needed   = next_level_pts - prev
    filled   = int(progress / needed * 10)
    bar      = "▓" * filled + "░" * (10 - filled)
    return f"[{bar}] {progress}/{needed}"


def leaderboard_text(period="week"):
    if period == "week":
        since = (datetime.now() - timedelta(days=7)).isoformat()
        title = "🏆  لیدربورد هفتگی"
    elif period == "month":
        since = (datetime.now() - timedelta(days=30)).isoformat()
        title = "🏆  لیدربورد ماهانه"
    else:
        since = "2000-01-01"
        title = "🌟  لیدربورد کل"

    rows = signals_repo.get_leaderboard_rows(since, limit=10)
    medals = ["🥇","🥈","🥉"] + ["🔹"]*7
    lines  = [f"<b>{title}</b>\n{SEP}\n\n"]
    if not rows:
        lines.append("📭  هنوز سیگنالی ثبت نشده\n")
    else:
        for i, (uid, name, uname, level, pts, cnt, wins) in enumerate(rows):
            display  = esc(name or (f"@{uname}" if uname else "کاربر"))
            winrate  = round(wins/cnt*100) if cnt else 0
            lines.append(
                f"{medals[i]} <b>{display}</b>  {level}\n"
                f"     ⭐️ <b>{pts or 0}</b> امتیاز  •  "
                f"📡 {cnt} سیگنال  •  ✅ {winrate}%  •  🎖 {alpha_score.get_label(uid)}\n\n"
            )
    lines.append(SEP)
    return "".join(lines)


def user_stats_text(user_id):
    user = users_repo.get_profile_fields(user_id)
    if not user:
        return "کاربری پیدا نشد."
    name, total_pts, streak, max_streak, level = user

    results = signals_repo.get_result_counts(user_id, status="approved")
    pending = signals_repo.count_user_signals(user_id, status="pending")
    rank = users_repo.get_rank(user_id) or "؟"
    role_label = access.get_role_label(users_repo.get_role(user_id))
    alpha_label = alpha_score.get_label(user_id)

    wins    = sum(v for k, v in results.items() if k and k.startswith("win"))
    losses  = results.get("loss", 0)
    winrate = round(wins/(wins+losses)*100, 1) if (wins+losses) > 0 else 0

    return (
        f"<b>👤  پروفایل {esc(name) or 'شما'}</b>\n{SEP}\n\n"
        f"رول: {role_label}\n"
        f"{level}\n"
        f"🎖  Alpha Score: <b>{alpha_label}</b>\n"
        f"📊  پیشرفت: {progress_bar(total_pts)}\n\n"
        f"{SEP}\n"
        f"⭐️  کل امتیاز    <b>{total_pts}</b>\n"
        f"🏅  رتبه کلی     <b>#{rank}</b>\n"
        f"🔥  استریک فعلی  <b>{streak}</b>\n"
        f"🏆  بهترین استریک <b>{max_streak}</b>\n\n"
        f"{SEP}\n"
        f"✅  سیگنال موفق  <b>{wins}</b>\n"
        f"❌  سیگنال ضرر   <b>{losses}</b>\n"
        f"📈  نرخ موفقیت   <b>{winrate}%</b>\n"
        f"⏳  در انتظار    <b>{pending}</b>\n\n"
        f"{SEP}\n"
        f"🚀  ۱۰ایکس  →  {results.get('win_10x',0)} سیگنال\n"
        f"💎  ۵ایکس   →  {results.get('win_5x',0)} سیگنال\n"
        f"✅  ۲ایکس   →  {results.get('win_2x',0)} سیگنال\n"
        f"{SEP}"
    )


def prize_pool_text():
    paid    = prize_repo.get_prize_pool_sum("paid")
    pending = prize_repo.get_prize_pool_sum("pending")
    season  = prize_repo.get_active_season()

    season_info = ""
    if season:
        end_date = datetime.fromisoformat(season[3])
        days_left = (end_date - datetime.now()).days
        season_info = (
            f"\n{SEP}\n"
            f"📅  دوره: <b>{season[1]}</b>\n"
            f"⏰  پایان: <b>{season[3][:10]}</b>"
            f"  ({max(0,days_left)} روز مانده)\n"
        )

    return (
        f"<b>💎  استخر جایزه</b>\n{SEP}\n\n"
        f"💰  تأییدشده:   <b>{paid:.2f} USDT</b>\n"
        f"⏳  در انتظار:  <b>{pending:.2f} USDT</b>\n"
        f"📊  کل استخر:  <b>{(paid+pending):.2f} USDT</b>\n"
        f"{season_info}\n"
        f"{SEP}\n"
        f"🥇  ۵۰٪  نفر اول\n"
        f"🥈  ۳۰٪  نفر دوم\n"
        f"🥉  ۲۰٪  نفر سوم\n"
        f"{SEP}"
    )


def hall_of_fame_text():
    rows = signals_repo.get_hall_of_fame_top(limit=5)
    winners = prize_repo.get_recent_winners(limit=6)

    medals = ["🥇","🥈","🥉","🔹","🔸"]
    lines  = [f"<b>🌟  تابلوی افتخار</b>\n{SEP2}\n\n"]
    lines.append("<b>👑  برترین‌های همه زمان</b>\n")
    for i, (uid, name, uname, level, pts, streak, cnt) in enumerate(rows):
        display = esc(name or (f"@{uname}" if uname else "کاربر"))
        lines.append(f"{medals[i]} <b>{display}</b> {level}\n"
                     f"     ⭐️{pts}  🔥استریک:{streak}  📡{cnt}  🎖{alpha_score.get_label(uid)}\n\n")

    if winners:
        lines.append(f"\n{SEP}\n<b>🏆  برندگان دوره‌های قبل</b>\n\n")
        for name, uname, rank, prize, season_name in winners:
            display = esc(name or (f"@{uname}" if uname else "کاربر"))
            medal   = ["🥇","🥈","🥉"][rank-1] if rank <= 3 else "🔹"
            lines.append(f"{medal} <b>{display}</b>  —  {prize:.1f}$  —  {esc(season_name)}\n")

    lines.append(f"\n{SEP2}")
    return "".join(lines)


def my_rewards_text(user_id):
    """تاریخچه پاداش‌های کاربر — کاملاً مستقل از استخر جایزه (بند ۱۲)."""
    rows = rewards_repo.list_for_user(user_id, limit=15)
    total = rewards_repo.get_total_for_user(user_id)

    if not rows:
        return f"<b>🎁  پاداش‌های من</b>\n{SEP}\n\n📭  هنوز پاداشی نگرفتی"

    lines = [f"<b>🎁  پاداش‌های من</b>\n{SEP}\n\n💰  مجموع: <b>{total}</b>\n\n{SEP}\n\n"]
    for rid, amount, reason, granted_at, status in rows:
        icon = "✅" if status == "paid" else "📝"
        lines.append(f"{icon}  <b>{amount}</b>  —  {esc(reason) or '—'}\n     🕐 {granted_at[:16]}\n\n")
    return "".join(lines)


def my_signals_text(user_id, filter_status="approved"):
    rows = signals_repo.get_user_signals(user_id, filter_status, limit=10)

    if not rows:
        return f"<b>📜  سیگنال‌های من ({filter_status})</b>\n{SEP}\n\n📭  چیزی پیدا نشد"

    lines = [f"<b>📜  سیگنال‌های من</b>\n{SEP}\n\n"]
    for sid, coin, direction, entry, sl, tp, result, pts, created, status, signal_type in rows:
        type_label = SIGNAL_TYPE_LABELS.get(signal_type, signal_type)
        dir_part = ""
        if direction:
            emoji = "🟢" if direction == "LONG" else "🔴"
            dir_part = f" {emoji} {direction}"
        price_part = ""
        if entry or sl or tp:
            price_part = f"💵{entry or '—'}  🛑{sl or '—'}  🎯{tp or '—'}\n"
        rlabel = RESULT_LABEL.get(result, result)
        lines.append(
            f"<b>#{sid}</b>  {type_label}  {esc(coin)}{dir_part}\n"
            f"{price_part}"
            f"نتیجه: {rlabel}  امتیاز: {pts:+}\n"
            f"🕐 {created[:16]}\n\n"
        )
    return "".join(lines)
