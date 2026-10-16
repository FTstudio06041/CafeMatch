"""
cafe_hours.py — 營業時間的判讀（今日時段、現在是否營業、一週總覽）

operatinghours 的慣例：
  day_of_week 1~7 = 週一~週日（與 isoweekday() 相同）
  一天可以有多列（例如午、晚分兩段）；is_closed=1 代表當天公休
  close_time 比 open_time 早 = 營業到隔天凌晨

時間一律用台灣時間判斷。台灣沒有日光節約，用固定 UTC+8，
不依賴 zoneinfo —— Windows 上沒裝 tzdata 時 zoneinfo 會直接失敗。

這裡只放純函式，不碰資料庫：呼叫端把 OperatingHours 列（或任何有
day_of_week / open_time / close_time / is_closed 屬性的物件）傳進來。
"""

from datetime import datetime, timedelta, timezone

TAIPEI_TZ = timezone(timedelta(hours=8))
DAY_LABELS = {1: '週一', 2: '週二', 3: '週三', 4: '週四', 5: '週五', 6: '週六', 7: '週日'}
MINUTES_PER_DAY = 24 * 60


def taipei_now():
    return datetime.now(TAIPEI_TZ)


def to_minutes(value):
    """把 time / timedelta（MySQL TIME 經 pymysql 有時會變成 timedelta）轉成當日分鐘數。"""
    if value is None:
        return None
    if isinstance(value, timedelta):
        return int(value.total_seconds() // 60) % MINUTES_PER_DAY
    if hasattr(value, 'hour') and hasattr(value, 'minute'):
        return value.hour * 60 + value.minute
    return None


def _fmt(minutes):
    return f'{minutes // 60:02d}:{minutes % 60:02d}'


def _sessions_for_day(rows, day):
    """回傳 (是否公休, [(開, 關), ...])；沒有任何資料時回傳 (None, [])。"""
    day_rows = [r for r in rows if r.day_of_week == day]
    if not day_rows:
        return None, []
    sessions = []
    for r in day_rows:
        if r.is_closed:
            continue
        start, end = to_minutes(r.open_time), to_minutes(r.close_time)
        if start is None or end is None:
            continue
        sessions.append((start, end))
    sessions.sort()
    # 有列、但沒有任何可用時段 = 公休
    return (not sessions), sessions


def describe_day(rows, day):
    closed, sessions = _sessions_for_day(rows, day)
    if closed is None:
        return None
    if closed:
        return '公休'
    return '、'.join(f'{_fmt(s)}–{_fmt(e)}' for s, e in sessions)


def weekly_hours(rows):
    """[{'day': 1, 'label': '週一', 'text': '11:00–21:00'}, ...]；完全沒資料回傳空串列。"""
    result = []
    for day in range(1, 8):
        text = describe_day(rows, day)
        if text is not None:
            result.append({'day': day, 'label': DAY_LABELS[day], 'text': text})
    return result


def is_open_at(rows, now):
    """
    回傳 True / False；當天與前一天都沒有資料時回傳 None（無法判斷）。

    除了當天的時段，也要看前一天跨午夜的時段 —— 週一 18:00–02:00 的店，
    週二凌晨一點也還開著。
    """
    day = now.isoweekday()
    prev_day = 7 if day == 1 else day - 1
    minute = now.hour * 60 + now.minute

    closed, sessions = _sessions_for_day(rows, day)
    _, prev_sessions = _sessions_for_day(rows, prev_day)
    if closed is None and not prev_sessions:
        return None

    for start, end in sessions:
        if start < end:
            if start <= minute < end:
                return True
        elif minute >= start:  # 跨午夜，今天開門後到午夜這段
            return True
    for start, end in prev_sessions:
        if end < start and minute < end:  # 前一天跨午夜延續到今天凌晨
            return True
    return False


def today_summary(rows, now=None):
    """首頁卡片用：{'today_hours': '11:00–21:00' | '今日公休' | None, 'is_open_now': bool | None}"""
    now = now or taipei_now()
    text = describe_day(rows, now.isoweekday())
    if text == '公休':
        text = '今日公休'
    return {'today_hours': text, 'is_open_now': is_open_at(rows, now)}
