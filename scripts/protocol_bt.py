"""
ALBA SCANNER PRO — Backtest del protocolo REAL
==============================================
Simula exactamente lo que se opera en vivo (alba_protocol.py): orden
límite desde la sesión siguiente, SL/TP con máximos y mínimos diarios,
gaps, costos y una posición por ticker a la vez.

Cada setup se compara contra ENTRADAS AL AZAR en tendencia con el mismo
bracket (si no le gana al azar, el setup no aporta nada), y se separa
in-sample (60% inicial del periodo) de out-of-sample (40% final).
Además compara varios brackets (ALBA 2/4, FIGAND 1,5/2, parcial+BE, 3/6).

Salida: data/protocol_bt.json — la usan check_alerts.py (frecuencias
calibradas y habilitación de setups) y la pestaña "Protocolo".
"""
import argparse, json, os, random, sys
from datetime import datetime, timezone

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import alba_protocol as ap

SETUPS_TESTED = ["RETROCESO", "RUPTURA", "IMPULSO", "IMPULSO_SIN_FILTRO"]
MIN_BARS = 260
WARMUP = 210


def _clean(df):
    if df is None or len(df) == 0:
        return None
    try:
        d = df[["Open", "High", "Low", "Close", "Volume"]].copy()
    except Exception:
        return None
    d = d.dropna(subset=["Open", "High", "Low", "Close"])
    d = d[(d["Close"] > 0) & (d["High"] >= d["Low"])]
    d = d[~d.index.duplicated(keep="last")].sort_index()
    return d if len(d) >= MIN_BARS else None


def _pack(trades, cut, n_sig=None):
    closed = [x for x in trades if not x.get("open") and x["status"] not in ("SIN FILL", "PENDIENTE")]
    nofill = sum(1 for x in trades if x["status"] == "SIN FILL")
    res = ap.summarize(closed)
    res["senales"] = int(n_sig if n_sig is not None else len(trades))
    res["ordenes"] = len(trades)
    res["tasa_fill"] = round((len(trades) - nofill) / len(trades) * 100, 1) if trades else None
    res["in_sample"] = ap.summarize([x for x in closed if x["date"] < cut])
    res["out_sample"] = ap.summarize([x for x in closed if x["date"] >= cut])
    if closed:
        st = {}
        for x in closed:
            st[x["status"]] = st.get(x["status"], 0) + 1
        res["por_estado"] = st
        years = {}
        for x in closed:
            years.setdefault(str(pd.Timestamp(x["date"]).year), []).append(x)
        res["por_anio"] = {y: {k: v for k, v in ap.summarize(v).items() if k in ("n", "acierto", "ret_medio", "p_tp")}
                           for y, v in sorted(years.items())}
    return res


def run(histories, params=None, seed=7, split=0.6, brackets=None, random_frac=0.04, log=print):
    """histories: {ticker: DataFrame OHLCV}. Devuelve el dict de resultados."""
    brackets = brackets or ap.BRACKETS_TEST
    prepared, d_first, d_last = {}, [], []
    for t, raw in histories.items():
        df = _clean(raw)
        if df is None:
            continue
        try:
            ind = ap.indicators(df)
            masks = ap.setups(ind, params)
        except Exception:
            continue
        prepared[t] = (df, ind, masks)
        d_first.append(df.index[WARMUP]); d_last.append(df.index[-1])
    if not prepared:
        return None
    d0, d1 = min(d_first), max(d_last)
    cut = d0 + (d1 - d0) * split
    log(f"  Protocolo: {len(prepared)} tickers · {str(d0)[:10]} → {str(d1)[:10]} · corte OOS {str(cut)[:10]}")

    out_br = {}
    for bname, bcfg in brackets.items():
        rng = random.Random(seed)
        per_setup = {s: [] for s in SETUPS_TESTED}
        n_sig = {s: 0 for s in SETUPS_TESTED}
        rand = []
        for t, (df, ind, masks) in prepared.items():
            o, h, l, c = (df[k].values.astype(float) for k in ("Open", "High", "Low", "Close"))
            atr = ind["atr"].values
            idx = df.index
            for s in SETUPS_TESTED:
                sig = np.flatnonzero(masks[s].values)
                sig = sig[(sig >= WARMUP) & (sig < len(c) - 1)]
                n_sig[s] += int(len(sig))
                busy = -1
                for i in sig:
                    if i <= busy:
                        continue
                    lv = ap.entry_levels(c[i], atr[i], bcfg)
                    r = ap.simulate(o, h, l, c, i, lv, bcfg)
                    busy = r.get("end", i)
                    r["date"] = idx[i]
                    per_setup[s].append(r)
            base = np.flatnonzero(masks["TENDENCIA"].values)
            base = base[(base >= WARMUP) & (base < len(c) - 1)]
            if len(base):
                pick = sorted(rng.sample(list(base), max(1, int(len(base) * random_frac))))
                busy = -1
                for i in pick:
                    if i <= busy:
                        continue
                    lv = ap.entry_levels(c[i], atr[i], bcfg)
                    r = ap.simulate(o, h, l, c, i, lv, bcfg)
                    busy = r.get("end", i)
                    r["date"] = idx[i]
                    rand.append(r)
        res = {s: _pack(per_setup[s], cut, n_sig[s]) for s in SETUPS_TESTED}
        res["AZAR"] = _pack(rand, cut)
        ref = res["AZAR"]
        for s in SETUPS_TESTED:
            x = res[s]
            x["vs_azar"] = (round(x["ret_medio"] - ref["ret_medio"], 3)
                            if x.get("n") and ref.get("n") else None)
            oos, roos = x.get("out_sample", {}), ref.get("out_sample", {})
            x["le_gana_al_azar"] = bool(
                x.get("n", 0) >= 30 and ref.get("n", 0) >= 30
                and x["ret_medio"] > ref["ret_medio"]
                and oos.get("n", 0) >= 15 and roos.get("n", 0) >= 15
                and oos["ret_medio"] > roos["ret_medio"])
            x["expectativa_positiva"] = bool(
                x.get("n", 0) >= 30 and x["ret_medio"] > 0
                and oos.get("n", 0) >= 15 and oos["ret_medio"] > 0)
        out_br[bname] = res
        log(f"    {bname}: " + " · ".join(
            f"{s} {res[s].get('ret_medio')}% (n={res[s].get('n')})" for s in SETUPS_TESTED + ["AZAR"]))

    alba = out_br.get("ALBA 2/4", {})
    return {
        "generado": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "tickers": len(prepared),
        "desde": str(pd.Timestamp(d0).date()), "hasta": str(pd.Timestamp(d1).date()),
        "corte_oos": str(pd.Timestamp(cut).date()),
        "bracket_alba": ap.BRACKET, "costo_pct": ap.COST_PCT,
        "brackets": out_br,
        # Resumen que consume check_alerts.py
        "habilitacion": {s: {
            "expectativa_positiva": alba.get(s, {}).get("expectativa_positiva", False),
            "le_gana_al_azar": alba.get(s, {}).get("le_gana_al_azar", False),
            "n": alba.get(s, {}).get("n", 0),
            "p_tp": alba.get(s, {}).get("p_tp"),
            "p_tp_ic95": alba.get(s, {}).get("p_tp_ic95"),
            "acierto": alba.get(s, {}).get("acierto"),
            "ret_medio": alba.get(s, {}).get("ret_medio"),
            "ret_medio_oos": alba.get(s, {}).get("out_sample", {}).get("ret_medio"),
            "dias_medios": alba.get(s, {}).get("dias_medios"),
        } for s in SETUPS_TESTED},
        "descripcion": ap.SETUP_INFO,
    }


def _safe(o):
    if isinstance(o, dict):
        return {str(k): _safe(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_safe(v) for v in o]
    if isinstance(o, (np.floating, np.integer)):
        o = o.item()
    if isinstance(o, float):
        return o if np.isfinite(o) else None
    if isinstance(o, (pd.Timestamp, datetime)):
        return str(o)[:10]
    return o


def save(result, out_dir):
    path = os.path.join(out_dir, "protocol_bt.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(_safe(result), f, ensure_ascii=False, allow_nan=False, separators=(",", ":"))
    return path


def main():
    a = argparse.ArgumentParser()
    a.add_argument("--out-dir", default="data")
    a.add_argument("--max-tickers", type=int, default=600)
    args = a.parse_args()
    import yfinance as yf
    snap = json.load(open(os.path.join(args.out_dir, "snapshot.json"), encoding="utf-8"))
    tick = []
    for rows in snap.get("groups", {}).values():
        for r in rows:
            if r["ticker"] not in tick:
                tick.append(r["ticker"])
    hist = {}
    for t in tick[: args.max_tickers]:
        try:
            sym = t.strip().upper().replace(".", "-").replace("/", "-").rstrip("*")
            hist[t] = yf.Ticker(sym).history(period="5y", auto_adjust=True)
        except Exception:
            pass
    res = run(hist)
    if res:
        print("Guardado:", save(res, args.out_dir))


if __name__ == "__main__":
    main()
