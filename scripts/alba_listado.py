#!/usr/bin/env python3
"""
ALBA — Candidatos del Listado completo (~11.500 símbolos)
=========================================================
figand_scan.py ya evaluó los setups Alba con precio en todo el Listado
(`alba_setups` en data/figand_scan.json). Pedir fundamentales a 11.500
símbolos tomaría horas; aquí se piden SOLO a los que hoy tienen setup y
pasan los filtros baratos:

  · no están ya en el universo principal (esos los cubre build_data.py)
  · precio ≥ ALBA_MIN_PRECIO (5 USD) y volumen en dólares ≥ ALBA_MIN_DOLAR_VOL_M
    (5 millones USD/día, promedio de 20 sesiones)
  · no son ETF apalancados o inversos
  · están en tendencia alcista (capa 1)
  · no tienen ya una alerta abierta

Como máximo ALBA_MAX_ENRIQUECER (150) por día, priorizando RETROCESO >
RUPTURA > IMPULSO y más liquidez. El resultado (data/listado_alba.json)
tiene el mismo formato que las filas del snapshot, así que check_alerts.py
les aplica exactamente las mismas cuatro capas.
"""
import json, math, os, sys, time, bisect
from datetime import datetime, timezone

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(BASE, "data")

MIN_PRICE = float(os.environ.get("ALBA_MIN_PRECIO", "5"))
MIN_DV = float(os.environ.get("ALBA_MIN_DOLAR_VOL_M", "5"))
MAX_ENRICH = int(os.environ.get("ALBA_MAX_ENRIQUECER", "150"))
OPEN_STATES = ("PENDIENTE", "ACTIVA", "TP1")


def load(name, default=None):
    try:
        with open(os.path.join(DATA, name), encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def json_safe(o):
    if isinstance(o, dict): return {k: json_safe(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)): return [json_safe(v) for v in o]
    if isinstance(o, (np.floating, np.integer)): o = o.item()
    if isinstance(o, float) and not math.isfinite(o): return None
    return o


def save(obj):
    with open(os.path.join(DATA, "listado_alba.json"), "w", encoding="utf-8") as f:
        json.dump(json_safe(obj), f, ensure_ascii=False, allow_nan=False, separators=(",", ":"))


def earnings(stock):
    """Próximo earnings (días, fecha) con la misma lógica de build_data."""
    try:
        cal = stock.calendar
        ed = None
        if isinstance(cal, dict):
            v = cal.get("Earnings Date") or cal.get("EarningsDate")
            if isinstance(v, (list, tuple)) and len(v) > 0:
                ed = v[0]
            elif v is not None:
                ed = v
        if ed is not None:
            edate = pd.Timestamp(ed).date()
            delta = (edate - datetime.now().date()).days
            if 0 <= delta <= 120:
                return int(delta), str(edate)
    except Exception:
        pass
    return None, None


def main():
    import yfinance as yf
    import build_data as bd
    print("═" * 58 + "\nALBA — candidatos del Listado completo\n" + "═" * 58)
    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    health = load("health.json", {}) or {}
    scan = load("figand_scan.json", {}) or {}
    snap = load("snapshot.json", {}) or {}
    hist = load("alerts_history.json", {"alerts": []}) or {"alerts": []}
    setups = scan.get("alba_setups") or []
    resumen = scan.get("alba_resumen") or {}
    base = {"generado": now, "session_ref": health.get("session_ref") or snap.get("session_ref"),
            "setups_listado": len(setups), "cobertura_pct": resumen.get("cobertura_pct"),
            "filtros": {"precio_min": MIN_PRICE, "dolar_vol_min_m": MIN_DV, "max_enriquecer": MAX_ENRICH},
            "rows": []}
    if health.get("status") == "FAILED":
        base["nota"] = "Datos del día incompletos: no se evalúan candidatos."
        save(base); print("  ⛔ " + base["nota"]); return
    if resumen.get("session_ref") and base["session_ref"] and resumen["session_ref"] != base["session_ref"]:
        base["nota"] = f"El escaneo del Listado es de la vela {resumen['session_ref']}, no de {base['session_ref']}."
        save(base); print("  ⚠️ " + base["nota"]); return

    main_rows = {}
    for rows in (snap.get("groups") or {}).values():
        for r in rows:
            main_rows.setdefault(r["ticker"], r)
    open_t = {a["ticker"] for a in hist.get("alerts", []) if a.get("status") in OPEN_STATES}
    spy = main_rows.get("SPY") or {}
    spy_3m = spy.get("perf_3m")
    rs_vals = sorted(r["rs_3m"] for r in main_rows.values() if r.get("rs_3m") is not None)

    motivos = {"universo_principal": 0, "precio": 0, "liquidez": 0, "apalancado": 0,
               "sin_tendencia": 0, "alerta_abierta": 0}
    cand = []
    for r in setups:
        t = r["ticker"]
        if t in main_rows: motivos["universo_principal"] += 1; continue
        if (r.get("close") or 0) < MIN_PRICE: motivos["precio"] += 1; continue
        if (r.get("dollar_vol_m") or 0) < MIN_DV: motivos["liquidez"] += 1; continue
        if r.get("apalancado"): motivos["apalancado"] += 1; continue
        if not (r.get("alba") or {}).get("tendencia"): motivos["sin_tendencia"] += 1; continue
        if t in open_t: motivos["alerta_abierta"] += 1; continue
        cand.append(r)
    print(f"  Setups en el Listado: {len(setups)} · pasan filtros: {len(cand)} · descartados: {motivos}")
    base["descartados"] = motivos
    base["candidatos_filtrados"] = len(cand)
    cand = cand[:MAX_ENRICH]

    out = []
    for i, r in enumerate(cand):
        t, close = r["ticker"], float(r["close"])
        row = {k: r.get(k) for k in ("ticker", "name", "sector", "industry", "close", "asof", "score",
                                     "ai", "rsi", "5d", "20d", "dollar_vol_m", "alba")}
        row.update({"origen": "Listado", "stale": False, "is_etf_listado": r.get("is_etf")})
        pe = roe = roa = eps_g = None
        bq, bq_v, mos = None, "⚪ SIN DATOS", None
        try:
            stock = yf.Ticker(bd.yf_symbol(t))
            info = stock.info or {}
            pe = bd.safe_float(info, "trailingPE")
            roe = bd.safe_pct(info, "returnOnEquity")
            roa = bd.safe_pct(info, "returnOnAssets")
            eps_g = bd.safe_pct(info, "earningsQuarterlyGrowth")
            row["name"] = (info.get("shortName") or row.get("name") or t)[:22]
            sec = info.get("sector")
            if not sec:
                qt = str(info.get("quoteType", "")).upper()
                sec = {"ETF": "ETF", "MUTUALFUND": "Fondo"}.get(qt, row.get("sector") or "N/A")
            row["sector"] = sec
            bq, bq_v, _, mos = bd.buffett_quality(info, close)
            row["earn_days"], row["earn_date"] = earnings(stock)
        except Exception as e:
            print(f"  ⚠️ {t}: {e}")
        if r.get("is_etf") and (row.get("sector") in (None, "", "N/A")):
            row["sector"] = "ETF"
        pe_gr, pe_pts = bd.grade_pe(pe)
        roe_gr, roe_pts = bd.grade_roe(roe)
        roa_gr, roa_pts = bd.grade_roa(roa)
        eps_gr, eps_pts = bd.grade_eps(eps_g)
        pts = [p for p in (pe_pts, roe_pts, roa_pts, eps_pts) if p is not None]
        row.update({
            "pe": round(pe, 1) if pe is not None else None, "pe_gr": pe_gr,
            "roe": round(roe, 1) if roe is not None else None, "roe_gr": roe_gr,
            "roa": round(roa, 1) if roa is not None else None, "roa_gr": roa_gr,
            "eps_g": round(eps_g, 1) if eps_g is not None else None, "eps_gr": eps_gr,
            "fund": round(sum(pts) / (len(pts) * 3) * 100) if pts else None,
            "buffett": bq, "buffett_v": bq_v, "mos": mos,
        })
        # Fuerza relativa vs SPY (3 meses), en el percentil del universo principal
        if r.get("ret63") is not None and spy_3m is not None:
            row["rs_3m"] = round(r["ret63"] - spy_3m, 2)
            if len(rs_vals) >= 10:
                row["rs_rank"] = round(bisect.bisect_left(rs_vals, row["rs_3m"]) / max(1, len(rs_vals) - 1) * 100)
        out.append(row)
        if (i + 1) % 25 == 0:
            print(f"  fundamentales {i + 1}/{len(cand)}", flush=True)
        time.sleep(0.25)
    base["rows"] = out
    base["enriquecidos"] = len(out)
    save(base)
    print(f"  ✅ data/listado_alba.json — {len(out)} candidatos con fundamentales")


if __name__ == "__main__":
    main()
