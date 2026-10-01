"""Calendario mínimo de la bolsa de EEUU (NYSE/Nasdaq) para Alba.
Solo se usa para saber qué sesión debería estar cerrada; si un festivo no
está en la lista, la referencia real la sigue dando la vela de SPY."""
from datetime import date, datetime, timedelta

NYSE_HOLIDAYS = {
    # 2026
    date(2026, 1, 1), date(2026, 1, 19), date(2026, 2, 16), date(2026, 4, 3),
    date(2026, 5, 25), date(2026, 6, 19), date(2026, 7, 3), date(2026, 9, 7),
    date(2026, 11, 26), date(2026, 12, 25),
    # 2027
    date(2027, 1, 1), date(2027, 1, 18), date(2027, 2, 15), date(2027, 3, 26),
    date(2027, 5, 31), date(2027, 6, 18), date(2027, 7, 5), date(2027, 9, 6),
    date(2027, 11, 25), date(2027, 12, 24),
}
CLOSE_MINUTES = 16 * 60 + 10   # 16:10 ET: cierre + margen


def now_et():
    try:
        from zoneinfo import ZoneInfo
        return datetime.now(ZoneInfo("America/New_York"))
    except Exception:
        return datetime.now()


def is_trading_day(d):
    return d.weekday() < 5 and d not in NYSE_HOLIDAYS


def expected_session_date(now=None):
    """Última sesión que ya debería estar CERRADA a la hora `now` (ET)."""
    now = now or now_et()
    d = now.date()
    if is_trading_day(d) and now.hour * 60 + now.minute >= CLOSE_MINUTES:
        return d
    d -= timedelta(days=1)
    while not is_trading_day(d):
        d -= timedelta(days=1)
    return d
