#!/usr/bin/env python3
"""
ALBA — Seguimiento de resultados de alertas (Historial del servidor)
====================================================================
Cada alerta se evalúa con EXACTAMENTE las mismas reglas del backtest
(alba_protocol.simulate), usando velas diarias reales:

  · La orden solo puede llenarse desde la sesión SIGUIENTE a la señal
    (FigAnd contaba el mínimo de la propia vela de la señal: 36 de 48
    fills eran imposibles).
  · Si abre bajo el límite, el fill es a la apertura; si abre bajo el
    stop, la orden se anula.
  · Día del fill: solo cuenta el stop. SL y TP el mismo día → SL.
  · Gap bajo el stop → sale a la apertura.
  · Resultado NETO de 0,2% de costos.

Estados: PENDIENTE · ACTIVA (abiertas) · TP2 (objetivo) · SL · EXPIRADA ·
SIN FILL. Las alertas heredadas de FigAnd se re-evalúan con su bracket
original (1,5/2 ATR, 7 sesiones de fill) pero con las reglas corregidas;
su resultado original queda guardado en `figand_original`.
"""
import json, os, math, sys
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import alba_protocol as ap

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(BASE, "data")
VERSION = 2
LEGACY_RULES = {"bracket": "FIGAND 1,5/2", "fill_window": 7, "expiry": 45}
ALBA_RULES = {"bracket": "ALBA 2/4", "fill_window": ap.BRACKET["fill_window"], "expiry": ap.BRACKET["expiry"]}
OPEN_STATES = ("PENDIENTE", "ACTIVA", "TP1")


def json_safe(o):
    if isinstance(o, dict): return {k: json_safe(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)): return [json_safe(v) for v in o]
    if isinstance(o, float) and not math.isfinite(o): return None
    return o


def load(name, default):
    try:
        with open(os.path.join(DATA, name), encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def yf_symbol(t):
    t = str(t).strip().upper().rstrip("*").replace("/", "-")
    if "." in t:
        base, suf = t.rsplit(".", 1)
        return f"{base}.{suf}" if (len(suf) >= 2 or base.isdigit()) else f"{base}-{suf}"
    return t


def now_et():
    try:
        from zoneinfo import ZoneInfo
        return datetime.now(ZoneInfo("America/New_York"))
    except Exception:
        return datetime.now()


def session_open(n):
    return n.weekday() < 5 and (9 * 60 + 30) <= n.hour * 60 + n.minute < (16 * 60 + 10)


def migrate(a):
    """Convierte una alerta de FigAnd al formato v2 y la deja lista para re-evaluar."""
    if a.get("v") == VERSION:
        return False
    a["figand_original"] = {k: a.get(k) for k in ("status", "fill_date", "outcome_date", "result_pct")}
    a["reglas"] = dict(LEGACY_RULES)
    a["tp"] = a.get("tp2")
    a.setdefault("setup", "IMPULSO (FigAnd)")
    for k in ("fill_date", "outcome_date", "result_pct", "live_pct", "tp1_date", "fill_px", "exit_px"):
        a[k] = None
    a["status"] = "PENDIENTE"
    a["v"] = VERSION
    return True


def main():
    print("═" * 55 + "\nALBA — SEGUIMIENTO DE ALERTAS (reglas del backtest)\n" + "═" * 55)
    hist = load("alerts_history.json", {"alerts": []})
    alerts_now = load("alerts.json", {})
    existing = {a.get("id") for a in hist["alerts"]}

    # ── 0) Migración de alertas heredadas (FigAnd) ──
    migrated = sum(1 for a in hist["alerts"] if migrate(a))
    if migrated:
        print(f"  Migradas y reiniciadas para re-evaluar con reglas corregidas: {migrated}")

    # ── 1) Registrar señales nuevas del último chequeo ──
    added = 0
    for s in alerts_now.get("signals", []):
        aid = f"{s['ticker']}_{s.get('asof') or alerts_now.get('checked_at', '')[:10]}"
        if aid in existing:
            continue
        z = s.get("zones") or {}
        if not z.get("entry") or not z.get("sl") or not (z.get("tp") or z.get("tp2")):
            continue
        hist["alerts"].append({
            "id": aid, "v": VERSION, "ticker": s["ticker"], "asof": s.get("asof"),
            "alerted_at": alerts_now.get("checked_at"),
            "setup": s.get("setup"), "sector": s.get("sector"),
            "entry": z["entry"], "sl": z["sl"], "tp": z.get("tp") or z.get("tp2"),
            "tp1": None, "tp2": z.get("tp") or z.get("tp2"),
            "reglas": dict(s.get("reglas") or ALBA_RULES),
            "stats": s.get("stats"), "fg": s.get("fg"),
            "buffett": s.get("buffett"), "rs_rank": s.get("rs_rank"),
            "status": "PENDIENTE", "fill_date": None, "outcome_date": None,
            "result_pct": None, "live_pct": None,
        })
        existing.add(aid); added += 1
    print(f"  Nuevas registradas: {added} | total en historial: {len(hist['alerts'])}")

    # ── 2) Evaluar las abiertas con velas diarias reales ──
    open_alerts = [a for a in hist["alerts"] if a["status"] in OPEN_STATES]
    yf = None
    if open_alerts:
        try:
            import yfinance as yf  # noqa
        except Exception:
            print("  ⚠️ yfinance no disponible — solo registro, sin seguimiento.")
            open_alerts = []
    cache, tracked = {}, 0
    n_et = now_et()
    for a in open_alerts:
        try:
            start = a.get("asof") or (a.get("alerted_at") or "")[:10]
            if not start:
                continue
            key = a["ticker"]
            if key not in cache:
                s0 = (datetime.strptime(min(x.get("asof") or start for x in open_alerts
                                            if x["ticker"] == key), "%Y-%m-%d") - timedelta(days=12)).strftime("%Y-%m-%d")
                df = yf.Ticker(yf_symbol(key)).history(start=s0, auto_adjust=True)
                if df is not None and len(df):
                    df = df.dropna(subset=["Open", "High", "Low", "Close"])
                    df = df[~df.index.duplicated(keep="last")].sort_index()
                cache[key] = df
            df = cache[key]
            if df is None or len(df) < 2:
                continue
            dates = [str(x.date()) for x in df.index]
            idx = [i for i, d in enumerate(dates) if d <= start]
            if not idx:
                continue
            i0 = idx[-1]
            r_ = a.get("reglas") or LEGACY_RULES
            bracket = {"fill_window": int(r_.get("fill_window", 5)), "expiry": int(r_.get("expiry", 45)),
                       "tp1_atr": None}
            lv = {"entry": a["entry"], "sl": a["sl"], "tp": a.get("tp") or a.get("tp2"), "tipo_orden": "LIMITE"}
            o, h, l, c = (df[k].values.astype(float) for k in ("Open", "High", "Low", "Close"))
            res = ap.simulate(o, h, l, c, i0, lv, bracket)
            partial_today = session_open(n_et) and dates[-1] == str(n_et.date())
            st = res["status"]
            if partial_today and res.get("end") == len(c) - 1 and st in ("SIN FILL", "EXPIRADA"):
                st = "PENDIENTE" if st == "SIN FILL" else "ACTIVA"      # la vela de hoy aún no termina
                res["open"] = True
            st = {"TP": "TP2"}.get(st, st)
            a["status"] = st
            if res.get("fill_i") is not None:
                a["fill_date"] = dates[res["fill_i"]]
                a["fill_px"] = round(res["fill_px"], 2)
            if res.get("open"):
                a["live_pct"] = round(res["ret"], 2) if res.get("ret") is not None else None
                a["outcome_date"] = None; a["result_pct"] = None
            else:
                a["outcome_date"] = dates[min(res["end"], len(dates) - 1)]
                if st == "SIN FILL":
                    a["result_pct"] = None
                else:
                    a["result_pct"] = round(res["ret"], 2)
                    a["exit_px"] = round(res.get("exit_px", 0), 2)
                a["live_pct"] = None
            tracked += 1
        except Exception as e:
            print(f"  ⚠️ {a['ticker']}: {e}")

    # ── 3) Resumen honesto ──
    al = hist["alerts"]
    closed = [a for a in al if a["status"] in ("TP2", "SL", "BE", "EXPIRADA") and a.get("result_pct") is not None]

    def block(xs):
        if not xs:
            return {"n": 0}
        rets = [x["result_pct"] for x in xs]
        w = [r for r in rets if r > 0]; lo = [r for r in rets if r <= 0]
        return {
            "n": len(xs),
            "acierto": round(len(w) / len(xs) * 100, 1),
            "acierto_ic95": ap.wilson(len(w), len(xs)),
            "p_tp": round(sum(1 for x in xs if x["status"] == "TP2") / len(xs) * 100, 1),
            "expectativa_pct": round(sum(rets) / len(xs), 2),
            "ganancia_media": round(sum(w) / len(w), 2) if w else None,
            "perdida_media": round(sum(lo) / len(lo), 2) if lo else None,
            "profit_factor": round(sum(w) / -sum(lo), 2) if lo and sum(lo) < 0 else None,
            "suma_pct": round(sum(rets), 1),
        }
    por_bracket, por_setup = {}, {}
    for x in closed:
        por_bracket.setdefault((x.get("reglas") or {}).get("bracket", "?"), []).append(x)
        por_setup.setdefault(x.get("setup") or "?", []).append(x)
    wins = [a for a in al if a["status"] == "TP2"]
    losses = [a for a in al if a["status"] == "SL"]
    hist["summary"] = {
        "updated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "reglas": "Fill solo desde la sesión siguiente · día del fill solo cuenta el SL · SL gana empates · gaps reales · resultado neto de 0,2%",
        "total": len(al),
        "activas": sum(1 for a in al if a["status"] in OPEN_STATES),
        "pendientes": sum(1 for a in al if a["status"] == "PENDIENTE"),
        "cerradas": len(closed),
        "tp1_parciales": 0,
        "wins_tp2": len(wins),
        "losses_sl": len(losses),
        "sin_fill": sum(1 for a in al if a["status"] == "SIN FILL"),
        "expiradas": sum(1 for a in al if a["status"] == "EXPIRADA"),
        "win_rate": round(len([x for x in closed if x["result_pct"] > 0]) / len(closed) * 100, 1) if closed else None,
        "avg_win_pct": round(sum(a["result_pct"] for a in wins) / len(wins), 2) if wins else None,
        "avg_loss_pct": round(sum(a["result_pct"] for a in losses) / len(losses), 2) if losses else None,
        "expectativa_pct": block(closed).get("expectativa_pct"),
        "global": block(closed),
        "por_bracket": {k: block(v) for k, v in por_bracket.items()},
        "por_setup": {k: block(v) for k, v in por_setup.items()},
    }
    hist["alerts"] = al[-1500:]
    with open(os.path.join(DATA, "alerts_history.json"), "w", encoding="utf-8") as f:
        json.dump(json_safe(hist), f, ensure_ascii=False, allow_nan=False, separators=(",", ":"))
    s = hist["summary"]
    print(f"  Seguidas: {tracked} | TP2: {s['wins_tp2']} | SL: {s['losses_sl']} | "
          f"sin fill: {s['sin_fill']} | acierto: {s['win_rate']}% | expectativa: {s['expectativa_pct']}%")


if __name__ == "__main__":
    main()
