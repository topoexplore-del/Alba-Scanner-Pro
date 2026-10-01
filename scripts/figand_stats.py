#!/usr/bin/env python3
"""
FIGAND STATS — recalcula los perfiles estadísticos con el historial propio.

Cierra el circuito de la arquitectura:
   señales → historial → análisis → motor de reglas → scanner diario

Parte de los perfiles semilla extraídos del estudio del Excel y les suma las
operaciones que el propio sistema va cerrando (data/alerts_history.json).
Cada perfil recalcula: casos, WIN, LOSS, win rate observado, límite inferior
de Wilson al 95% y probabilidad estimada (contracción bayesiana hacia la tasa
base). La etiqueta "combo" es DINÁMICA: se otorga por criterio estadístico,
no por texto fijo.

Criterio combo:  n ≥ 12 cerradas  ·  Wilson 95% ≥ tasa base + 5 pts
"""
import json, math, os

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(BASE, "data")
MIN_N_COMBO = 12
EDGE_MIN = 0.05

def wilson(w, n, z=1.96):
    if n == 0: return 0.0
    p = w / n; d = 1 + z*z/n
    c = p + z*z/(2*n)
    m = z*math.sqrt(p*(1-p)/n + z*z/(4*n*n))
    return max(0.0, (c-m)/d)

def shrink(w, n, base, k=12):
    return (w + k*base) / (n + k) if n + k > 0 else base

def cond_ok(cid, fg):
    """Evalúa una condición sobre las variables FIGAND guardadas en la señal."""
    if not fg: return None
    if cid == "not_temprano":    return fg.get("not_temprano")
    if cid == "fase_acumulacion":return fg.get("fase") == "Acumulación" if fg.get("fase") else None
    if cid == "markov_bullish":  return fg.get("markov") == 2 if fg.get("markov") is not None else None
    if cid == "dif_ema_gt_-2":   return fg["dif_ema"] > -2 if fg.get("dif_ema") is not None else None
    if cid == "calidad_excelente": return fg.get("calidad") == "EXCELENTE" if fg.get("calidad") else None
    if cid == "upside_12":       return fg["upside"] >= 12 if fg.get("upside") is not None else None
    if cid == "laplace_buy":     return None
    if cid == "estab_unstable":  return None
    return None

def main():
    path = os.path.join(DATA, "figand_profiles.json")
    prof = json.load(open(path, encoding="utf-8"))
    try:
        hist = json.load(open(os.path.join(DATA, "alerts_history.json"), encoding="utf-8"))
        alerts = hist.get("alerts", [])
    except Exception:
        alerts = []

    # Solo operaciones del protocolo con el que se hizo el estudio (bracket FigAnd 1,5/2):
    # las alertas Alba (2/4) tienen otra tasa base y mezclarlas falsearía los perfiles.
    cerradas = [a for a in alerts if a.get("status") in ("TP2", "SL") and a.get("fg")
                and str((a.get("reglas") or {}).get("bracket", "FIGAND")).startswith("FIGAND")]
    print("═" * 58 + "\nFIGAND STATS — recálculo de perfiles\n" + "═" * 58)
    print(f"  Operaciones propias cerradas con variables FIGAND: {len(cerradas)}")

    # Tasa base: semilla del estudio + operaciones propias
    sw = prof.get("seed_wins", 86); sl = prof.get("seed_losses", 96)
    lw = sum(1 for a in cerradas if a["status"] == "TP2")
    ll = sum(1 for a in cerradas if a["status"] == "SL")
    base = (sw + lw) / max(1, sw + sl + lw + ll)
    prof["seed_wins"], prof["seed_losses"] = sw, sl
    prof["live_wins"], prof["live_losses"] = lw, ll
    prof["base_win_rate"] = round(base, 4)
    prof["n_cerradas_total"] = sw + sl + lw + ll

    for p in prof["perfiles"]:
        if p.get("activo") is False:
            p["combo"] = False
            continue
        p.setdefault("seed_win", p["win"]); p.setdefault("seed_loss", p["loss"])
        p.setdefault("seed_casos", p["casos"]); p.setdefault("seed_pct", p["pct"])
        w = l = 0; pnl = []
        for a in cerradas:
            res = [cond_ok(c, a["fg"]) for c in p["cond"]]
            if all(x is True for x in res):
                if a["status"] == "TP2": w += 1
                else: l += 1
                if a.get("result_pct") is not None:
                    pnl.append(a["result_pct"] / 100.0)
        p["live_win"], p["live_loss"] = w, l
        p["win"] = p["seed_win"] + w
        p["loss"] = p["seed_loss"] + l
        p["casos"] = p["seed_casos"] + w + l
        n = p["win"] + p["loss"]
        p["n_cerradas"] = n
        p["wr"] = round(p["win"] / n, 4) if n else 0
        p["wr_lo"] = round(wilson(p["win"], n), 4)
        p["wr_est"] = round(shrink(p["win"], n, base), 4)
        p["edge"] = round(p["wr_est"] - base, 4)
        p["confianza"] = "ALTA" if n >= 40 else ("MEDIA" if n >= 20 else "BAJA")
        if pnl:
            tot = p["seed_pct"] * (p["seed_win"] + p["seed_loss"]) + sum(pnl)
            p["pct"] = round(tot / n, 5) if n else p["seed_pct"]
        # ── Etiqueta combo DINÁMICA: criterio estadístico, no texto fijo ──
        antes = p.get("combo", False)
        p["combo"] = bool(n >= MIN_N_COMBO and p["wr_lo"] >= base + EDGE_MIN)
        if antes != p["combo"]:
            print(f"  ⚠ {p['id']} cambia de clasificación: combo={'SÍ' if p['combo'] else 'NO'}")

    prof["perfiles"].sort(key=lambda x: -x["wr_lo"])
    json.dump(prof, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"  Tasa base actualizada: {base:.1%} sobre {prof['n_cerradas_total']} cerradas")
    print(f"  {'ID':4s} {'perfil':42s} {'n':>4s} {'WR':>7s} {'Wilson':>7s} {'est':>6s}  combo")
    for p in prof["perfiles"]:
        if p.get("activo") is False:
            print(f"  {p['id']:4s} {p['nombre'][:42]:42s} — desactivado: {p.get('motivo','')[:60]}")
            continue
        print(f"  {p['id']:4s} {p['nombre'][:42]:42s} {p['n_cerradas']:4d} {p['wr']:6.1%} {p['wr_lo']:6.1%} {p['wr_est']:5.1%}  {'✅' if p['combo'] else '—'}")

if __name__ == "__main__":
    main()
