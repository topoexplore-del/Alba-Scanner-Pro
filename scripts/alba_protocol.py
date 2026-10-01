"""
ALBA SCANNER PRO — Protocolo de señal y simulador de operaciones
=================================================================
Un solo lugar define (1) los indicadores, (2) los setups de entrada,
(3) los niveles de la orden y (4) cómo se simula una operación. Lo usan:

  · build_data.py   → clasifica la última vela de cada ticker (señal en vivo)
  · protocol_bt.py  → backtest del protocolo REAL (el mismo que se opera)
  · track_alerts.py → seguimiento de las alertas con las MISMAS reglas

Así el backtest, las alertas y el historial hablan exactamente el mismo idioma.
No depende de yfinance: solo pandas/numpy sobre velas diarias OHLCV.

Bracket Alba (elegido con datos, ver MANUAL_ALBA.md):
  · Orden límite en cierre − 0,3 ATR, válida 5 sesiones, SOLO desde la
    sesión siguiente a la señal. Si abre por debajo del límite → fill a la
    apertura. Si abre por debajo del stop → la orden se anula.
  · SL = entrada − 2 ATR · TP = entrada + 4 ATR (riesgo/beneficio 1:2).
    Punto de equilibrio: 33,3% de aciertos + costos.
  · Sin TP1 parcial ni stop a la entrada: en 4 años de datos (498 acciones
    del S&P 500) esa gestión recortó las ganadoras y bajó la expectativa.
  · Día del fill: solo cuenta el SL (no se sabe si el máximo fue antes).
  · SL y TP el mismo día → gana el SL (conservador).
  · Gap bajo el stop → sale a la apertura (peor precio, realista).
  · 45 sesiones sin desenlace → se cierra al último cierre (EXPIRADA).
  · Costo ida y vuelta: 0,2%.
"""
import numpy as np
import pandas as pd

COST_PCT = 0.2
BRACKET = {
    "entry_atr": 0.3,     # límite = cierre − 0,3 ATR
    "sl_atr": 2.0,
    "tp_atr": 4.0,
    "tp1_atr": None,      # None = sin salida parcial
    "be_after_tp1": True, # solo aplica si tp1_atr no es None
    "fill_window": 5,     # sesiones para que se llene la orden
    "expiry": 45,         # sesiones máximas tras el fill
}

# Variantes que el backtest diario compara sobre el universo real
BRACKETS_TEST = {
    "ALBA 2/4": {},
    "FIGAND 1,5/2": {"sl_atr": 1.5, "tp_atr": 2.0, "fill_window": 7},
    "PARCIAL+BE 1/1,5/2": {"sl_atr": 1.5, "tp1_atr": 1.0, "tp_atr": 2.0, "fill_window": 7},
    "AMPLIO 3/6": {"sl_atr": 3.0, "tp_atr": 6.0},
}

SETUP_INFO = {
    "RETROCESO": "Tendencia alcista intacta; el precio volvió a la EMA20 en los últimos 3 días y hoy gira al alza (vela verde, RSI subiendo, RSI 40–60). Es la entrada más temprana.",
    "RUPTURA": "Base estrecha de 20 días (rango ≤ 6 ATR) que se rompe al cierre con volumen ≥ 1,5× y sin estiramiento.",
    "IMPULSO": "Momentum confirmado (réplica técnica del 4/4 de FigAnd) con filtro anti-extensión.",
    "AZAR": "Referencia: velas al azar en tendencia alcista con el mismo bracket. Un setup solo aporta si le gana.",
}
SETUP_PRIORITY = ("RETROCESO", "RUPTURA", "IMPULSO")


# ═══ INDICADORES (idénticos a compute_score de FigAnd + extras) ════════
def indicators(df):
    """DataFrame de indicadores por vela. df: Open, High, Low, Close, Volume."""
    o, h, l, c, v = df["Open"], df["High"], df["Low"], df["Close"], df["Volume"]
    ema10 = c.ewm(span=10, adjust=False).mean()
    ema20 = c.ewm(span=20, adjust=False).mean()
    ema50 = c.ewm(span=50, adjust=False).mean()
    ema200 = c.ewm(span=200, adjust=False).mean()
    sma20 = c.rolling(20).mean()
    sma50 = c.rolling(50).mean()
    sma200 = c.rolling(200).mean()
    delta = c.diff()
    gain = delta.clip(lower=0).ewm(alpha=1/14, min_periods=14, adjust=False).mean()
    loss = (-delta).clip(lower=0).ewm(alpha=1/14, min_periods=14, adjust=False).mean()
    rsi = 100 - 100 / (1 + gain / loss.replace(0, np.nan))
    tr = pd.concat([h - l, (h - c.shift()).abs(), (l - c.shift()).abs()], axis=1).max(axis=1)
    atr = tr.ewm(alpha=1/14, min_periods=14, adjust=False).mean()
    up = h.diff(); dn = -l.diff()
    pdm = pd.Series(np.where((up > dn) & (up > 0), up, 0), index=df.index)
    ndm = pd.Series(np.where((dn > up) & (dn > 0), dn, 0), index=df.index)
    pdi = 100 * pdm.ewm(alpha=1/14, min_periods=14, adjust=False).mean() / atr.replace(0, np.nan)
    ndi = 100 * ndm.ewm(alpha=1/14, min_periods=14, adjust=False).mean() / atr.replace(0, np.nan)
    dx = 100 * (pdi - ndi).abs() / (pdi + ndi).replace(0, np.nan)
    adx = dx.ewm(alpha=1/14, min_periods=14, adjust=False).mean()
    bb_basis = c.rolling(20).mean()
    bb_w = (4 * c.rolling(20).std()) / bb_basis
    bb_w_low = bb_w.rolling(50).min()
    vol_ma = v.rolling(20).mean()
    rel_vol = v / vol_ma.replace(0, np.nan)
    obv = (np.sign(c.diff()) * v).cumsum()
    obv_sma = obv.rolling(10).mean()
    h20 = h.rolling(20).max()
    s_trend = ((ema50 > ema200) & (c > ema200)).astype(int) * 30
    s_mom = ((rsi > 50) & (rsi < 70)).astype(int) * 15
    s_adx = ((adx > 18) & (adx < 35)).astype(int) * 15
    s_comp = (bb_w < bb_w_low * 1.2).astype(int) * 15
    s_accum = ((obv > obv_sma) & (rel_vol > 1)).astype(int) * 15
    s_brk = (c > h20 * 0.97).astype(int) * 10
    score = s_trend + s_mom + s_adx + s_comp + s_accum + s_brk
    ext = (c - ema50) / ema50 * 100
    mz = (rsi - 50) / 10
    ts = (ema50 - ema200) / ema200.replace(0, np.nan)
    vr = bb_w / bb_w.rolling(50).mean().replace(0, np.nan)
    raw = mz * 0.8 + ts * 5 + (rel_vol - 1) * 1.2 + adx / 25
    ai = ((100 / (1 + np.exp(-raw))) * (1 + (vr - 1) * 0.5)).clip(5, 95)
    out = pd.DataFrame({
        "open": o, "high": h, "low": l, "close": c, "volume": v,
        "ema10": ema10, "ema20": ema20, "ema50": ema50, "ema200": ema200,
        "sma20": sma20, "sma50": sma50, "sma200": sma200,
        "rsi": rsi, "adx": adx, "atr": atr, "rel_vol": rel_vol,
        "bb_w": bb_w, "bb_w_low": bb_w_low, "score": score, "ai": ai, "ext": ext,
    })
    out["ret5"] = (c / c.shift(5) - 1) * 100
    out["ret20"] = (c / c.shift(20) - 1) * 100
    out["hh20_prev"] = h.shift(1).rolling(20).max()
    out["ll20_prev"] = l.shift(1).rolling(20).min()
    out["atr_pct"] = atr / c * 100
    out["dist20_atr"] = (c - ema20) / atr.replace(0, np.nan)
    out["base_rng_atr"] = (out["hh20_prev"] - out["ll20_prev"]) / atr.replace(0, np.nan)
    out["rsi_prev"] = rsi.shift(1)
    out["low_min3"] = l.rolling(3).min()
    return out


# ═══ SETUPS ════════════════════════════════════════════════════════════
DEFAULT_PARAMS = {
    "pb_rsi_lo": 40, "pb_rsi_hi": 60, "pb_touch_atr": 0.35, "pb_max_dist_atr": 0.9,
    "br_base_atr": 6.0, "br_relvol": 1.5, "br_max_ext": 8.0, "br_max_dist_atr": 1.6,
    "ae_max_dist_atr": 1.6, "ae_max_rsi": 70,
}


def setups(ind, params=None):
    """Máscaras booleanas por vela (evaluadas al cierre de esa vela)."""
    p = dict(DEFAULT_PARAMS, **(params or {}))
    c = ind["close"]
    trend = (c > ind["sma200"]) & (ind["sma50"] > ind["sma200"]) & (ind["ema20"] > ind["sma50"])
    touched = ind["low_min3"] <= ind["ema20"] + p["pb_touch_atr"] * ind["atr"]
    pullback = (
        trend & touched
        & (c > ind["ema20"]) & (ind["dist20_atr"] <= p["pb_max_dist_atr"])
        & (c > ind["open"]) & (ind["rsi"] > ind["rsi_prev"])
        & (ind["rsi"] >= p["pb_rsi_lo"]) & (ind["rsi"] <= p["pb_rsi_hi"])
        & (ind["ret5"] <= 1.0)
    )
    breakout = (
        (c > ind["sma50"]) & (ind["sma50"] > ind["sma200"])
        & (ind["base_rng_atr"] <= p["br_base_atr"])
        & (c > ind["hh20_prev"]) & (ind["rel_vol"] >= p["br_relvol"])
        & (ind["ext"] <= p["br_max_ext"]) & (ind["dist20_atr"] <= p["br_max_dist_atr"])
        & (ind["rsi"] < 72)
    )
    anti_ext = (ind["dist20_atr"] <= p["ae_max_dist_atr"]) & (ind["rsi"] <= p["ae_max_rsi"])
    st_entry = (ind["score"] >= 75) & (ind["ai"] > 70) & (ind["ext"] < 12)
    tgt = (c + 3 * ind["atr"]) * np.where((ind["score"] >= 75) & (ind["ai"] > 70), 1.05, 1.0)
    upside = (tgt / c - 1) * 100
    abc_ok = ~((ind["ema10"] < ind["ema20"]) & (ind["ema20"] < ind["sma50"]))
    impulso = (st_entry & (ind["score"] >= 60) & (ind["ai"] >= 65) & abc_ok
               & (ind["rsi"] < 75) & (upside >= 8) & (ind["ret20"] > 0) & (ind["ret5"] > -5))
    valid = ind["atr"].notna() & ind["sma200"].notna() & (ind["atr"] > 0)
    return {
        "RETROCESO": (pullback & anti_ext & valid).fillna(False),
        "RUPTURA": (breakout & anti_ext & valid).fillna(False),
        "IMPULSO": (impulso & anti_ext & valid).fillna(False),
        "IMPULSO_SIN_FILTRO": (impulso & valid).fillna(False),
        "TENDENCIA": (trend & valid).fillna(False),
    }


def entry_levels(close, atr, bracket=None):
    """Niveles de la orden (dict) a partir del cierre y ATR de la vela de señal."""
    b = dict(BRACKET, **(bracket or {}))
    close, atr = float(close), float(atr)
    entry = close - b["entry_atr"] * atr
    lv = {
        "tipo_orden": "LIMITE", "entry": round(entry, 2),
        "sl": round(entry - b["sl_atr"] * atr, 2),
        "tp": round(entry + b["tp_atr"] * atr, 2),
        "tp1": round(entry + b["tp1_atr"] * atr, 2) if b.get("tp1_atr") else None,
        "atr": round(atr, 4),
    }
    lv["tp2"] = lv["tp"]        # compatibilidad con FigAnd (dashboard/historial)
    return lv


# ═══ SIMULADOR DE UNA OPERACIÓN ════════════════════════════════════════
def simulate(o, h, l, c, start, lv, bracket=None):
    """Simula una orden colocada tras el cierre de la vela `start`.
    o,h,l,c: arrays numpy de la serie. lv: dict con entry, sl, tp (y tp1 opcional).
    status: SIN FILL · PENDIENTE · ACTIVA · TP1 (abiertas) · SL · BE · TP · EXPIRADA"""
    b = dict(BRACKET, **(bracket or {}))
    n = len(c)
    E, SL = float(lv["entry"]), float(lv["sl"])
    T = float(lv.get("tp") or lv.get("tp2"))
    T1 = lv.get("tp1") if b.get("tp1_atr") or lv.get("tp1_forzado") else None
    T1 = float(T1) if T1 else None
    fill_i, fill_px, at_open = None, None, False
    for k in range(start + 1, min(start + 1 + b["fill_window"], n)):
        if o[k] <= E:
            if o[k] <= SL:                       # abre bajo el stop: la orden se anula
                return {"status": "SIN FILL", "end": k, "open": False, "nota": "gap bajo el stop"}
            fill_i, fill_px, at_open = k, o[k], True
        elif l[k] <= E:
            fill_i, fill_px = k, E
        if fill_i is not None:
            break
    if fill_i is None:
        if start + b["fill_window"] < n:
            return {"status": "SIN FILL", "end": start + b["fill_window"], "open": False}
        return {"status": "PENDIENTE", "end": n - 1, "open": True}

    half, part1, stop, status = False, 0.0, SL, "ACTIVA"
    last = min(fill_i + b["expiry"], n - 1)
    for k in range(fill_i, last + 1):
        first = (k == fill_i)
        op, hi, lo = o[k], h[k], l[k]
        if not first and op <= stop:             # gap bajo el stop → sale a la apertura
            return _close("BE" if half else "SL", fill_i, k, fill_px, op, half, part1)
        if lo <= stop:
            return _close("BE" if half else "SL", fill_i, k, fill_px, stop, half, part1)
        if first and not at_open:                # día del fill intradía: sin objetivos
            continue
        if T1 and not half and hi >= T1:
            part1 = T1 if first else max(op, T1)
            half, status = True, "TP1"
            if b.get("be_after_tp1", True):
                stop = max(stop, E)
            if hi >= T:
                return _close("TP", fill_i, k, fill_px, T if first else max(op, T), half, part1)
            if lo <= stop:
                return _close("BE", fill_i, k, fill_px, stop, half, part1)
            continue
        if hi >= T:
            return _close("TP", fill_i, k, fill_px, T if first else max(op, T), half, part1)
    if fill_i + b["expiry"] <= n - 1:
        return _close("EXPIRADA", fill_i, last, fill_px, c[last], half, part1)
    return {"status": status, "fill_i": fill_i, "end": n - 1, "fill_px": float(fill_px),
            "ret": _ret(fill_px, c[n - 1], half, part1), "open": True}


def _ret(fill_px, exit_px, half, part1):
    if half:
        r = 0.5 * (part1 / fill_px - 1) + 0.5 * (exit_px / fill_px - 1)
    else:
        r = exit_px / fill_px - 1
    return float(r * 100 - COST_PCT)


def _close(status, fill_i, k, fill_px, exit_px, half, part1):
    return {"status": status, "fill_i": fill_i, "end": k, "days": int(k - fill_i),
            "fill_px": float(fill_px), "exit_px": float(exit_px),
            "ret": _ret(fill_px, exit_px, half, part1), "open": False}


# ═══ ESTADÍSTICAS ══════════════════════════════════════════════════════
def wilson(k, n, z=1.96):
    if not n:
        return [None, None]
    p = k / n
    den = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / den
    half = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return [round((centre - half) * 100, 1), round((centre + half) * 100, 1)]


def summarize(trades):
    """trades: dicts cerrados con 'ret' (% neto) y 'status'."""
    rets = np.array([t["ret"] for t in trades], dtype=float)
    if len(rets) == 0:
        return {"n": 0}
    wins, losses = rets[rets > 0], rets[rets <= 0]
    gw, gl = float(wins.sum()), float(-losses.sum())
    k_tp = sum(1 for t in trades if t["status"] == "TP")
    return {
        "n": int(len(rets)),
        "acierto": round(len(wins) / len(rets) * 100, 1),
        "acierto_ic95": wilson(len(wins), len(rets)),
        "p_tp": round(k_tp / len(rets) * 100, 1),
        "p_tp_ic95": wilson(k_tp, len(rets)),
        "ret_medio": round(float(rets.mean()), 3),
        "ganancia_media": round(float(wins.mean()), 2) if len(wins) else None,
        "perdida_media": round(float(losses.mean()), 2) if len(losses) else None,
        "profit_factor": round(gw / gl, 2) if gl > 0 else None,
        "dias_medios": round(float(np.mean([t.get("days", 0) for t in trades])), 1),
    }


# ═══ SEÑAL EN VIVO (última vela) ═══════════════════════════════════════
def live_setup(df, params=None, bracket=None):
    """Clasifica la ÚLTIMA vela cerrada de un ticker."""
    if df is None or len(df) < 220:
        return None
    ind = indicators(df)
    m = setups(ind, params)
    last = ind.iloc[-1]
    atr = float(last["atr"]) if np.isfinite(last["atr"]) else None
    if not atr or atr <= 0:
        return None
    found = next((s for s in SETUP_PRIORITY if bool(m[s].iloc[-1])), None)

    def r2(x):
        return round(float(x), 2) if x is not None and np.isfinite(x) else None
    res = {
        "setup": found,
        "tendencia": bool(m["TENDENCIA"].iloc[-1]),
        "dist20_atr": r2(last["dist20_atr"]),
        "atr_pct": r2(last["atr_pct"]),
        "base_rng_atr": r2(last["base_rng_atr"]),
        "niveles": entry_levels(last["close"], atr, bracket),
    }
    # días desde el último setup (para ver si una señal sigue vigente)
    any_setup = (m["RETROCESO"] | m["RUPTURA"] | m["IMPULSO"]).values
    idx = np.flatnonzero(any_setup)
    res["dias_desde_setup"] = int(len(any_setup) - 1 - idx[-1]) if len(idx) else None
    if found:
        res["desc"] = SETUP_INFO[found]
    return res
