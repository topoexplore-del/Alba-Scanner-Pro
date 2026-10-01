"""
ALBA SCANNER PRO — Sistema de alertas v1.0
==========================================
Cuatro capas, todas medibles:

  1. TENDENCIA  — precio > SMA200, SMA50 > SMA200 y EMA20 > SMA50.
  2. CALIDAD    — fundamentales (ROE, ROA, EPS, P/E); los ETF la omiten.
  3. SETUP      — RETROCESO, RUPTURA o IMPULSO en la vela de HOY
                  (alba_protocol.py), con filtro anti-extensión.
  4. RIESGO     — datos sanos, régimen de mercado, blackout de earnings,
                  una alerta abierta por ticker, máx. 2 por sector, máx. 5
                  nuevas por día, y setup con expectativa positiva en el
                  backtest del protocolo real (data/protocol_bt.json), y liquidez
                  mínima (precio ≥ 5 USD, ≥ 5 M USD/día; sin ETF apalancados).

Universo: los ~1.170 tickers del snapshot + los candidatos del Listado
completo (~11.500 símbolos) que hoy tienen setup (data/listado_alba.json,
generado por figand_scan.py + alba_listado.py). Mismas capas para todos.

Lo que ya NO hace (FigAnd): probabilidad "bayesiana" de 95%, EV con un
pago +3/−2 inexistente, Kelly de 92%, periodos con objetivos fijos.
La probabilidad que se muestra es la FRECUENCIA HISTÓRICA de que el
setup tocara el objetivo antes que el stop, con su intervalo de confianza.

Run: python scripts/check_alerts.py
"""
import json, os, smtplib, warnings, sys, math
import urllib.request
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timezone, timedelta

warnings.filterwarnings("ignore")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import alba_protocol as ap

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(BASE, "data")

EARNINGS_BLACKOUT_DAYS = int(os.environ.get("EARNINGS_BLACKOUT_DAYS", "5"))
MAX_NEW_PER_DAY = int(os.environ.get("ALBA_MAX_NUEVAS", "5"))
MAX_PER_SECTOR = int(os.environ.get("ALBA_MAX_SECTOR", "2"))
RISK_PCT = float(os.environ.get("ALBA_RIESGO_PCT", "1"))
ENABLED_SETUPS = [s.strip() for s in os.environ.get("ALBA_SETUPS", "RETROCESO,RUPTURA,IMPULSO").split(",") if s.strip()]
MIN_PRICE = float(os.environ.get("ALBA_MIN_PRECIO", "5"))
MIN_DV = float(os.environ.get("ALBA_MIN_DOLAR_VOL_M", "5"))
OPEN_STATES = ("PENDIENTE", "ACTIVA", "TP1")
import re as _re
LEVERAGED = _re.compile(r"(ULTRA|LEVERAGED|INVERSE|\b[1-3]X\b|DAILY|PROSHARES SHORT|\bBEAR\b)", _re.I)
BOGOTA = timezone(timedelta(hours=-5))


# ═══ HELPERS ═══════════════════════════════════════════════════
def json_safe(o):
    if isinstance(o, dict): return {k: json_safe(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)): return [json_safe(v) for v in o]
    if isinstance(o, float) and not math.isfinite(o): return None
    return o


def load(name, default=None):
    try:
        with open(os.path.join(DATA, name), "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def save(name, obj):
    with open(os.path.join(DATA, name), "w", encoding="utf-8") as f:
        json.dump(json_safe(obj), f, ensure_ascii=False, indent=1, allow_nan=False)


def yf_symbol(t):
    t = str(t).strip().upper().rstrip("*").replace("/", "-")
    if "." in t:
        base, suf = t.rsplit(".", 1)
        return f"{base}.{suf}" if (len(suf) >= 2 or base.isdigit()) else f"{base}-{suf}"
    return t


def grade_score(gr):
    if not gr: return 0
    g = gr.lower()
    if g in ("excel", "strong", "cheap"): return 5
    if g in ("good", "solid"): return 4
    if g in ("fair", "mod"): return 3
    if g in ("med", "pricey"): return 2
    return 1 if g != "n/a" else 0


def composite_score(r):
    raw = (grade_score(r.get("eps_gr", "")) * 0.30 + grade_score(r.get("roe_gr", "")) * 0.25 +
           grade_score(r.get("roa_gr", "")) * 0.20 + grade_score(r.get("pe_gr", "")) * 0.25)
    return round((raw / 5) * 100)


def is_etf_or_index(r):
    s = (r.get("sector") or "").lower()
    return s in ("index", "etf", "commodity", "fixed income", "", "índice", "fondo")


def live_price(ticker):
    try:
        import yfinance as yf
        fi = yf.Ticker(yf_symbol(ticker)).fast_info
        p = fi.get("last_price") if hasattr(fi, "get") else getattr(fi, "last_price", None)
        return round(float(p), 2) if p else None
    except Exception:
        return None


def classify_freshness(a):
    """Precio actual contra la zona: ¿la señal sigue operable?"""
    z = a.get("zones") or {}
    entry, tp, atr = z.get("entry"), z.get("tp"), z.get("atr")
    if not entry or not tp or not atr:
        return None
    max_chase = round(entry + 0.5 * atr, 2)
    lp = live_price(a["ticker"])
    a["live"], a["max_chase"] = lp, max_chase
    if lp is None:
        st = {"icon": "❔", "label": "SIN COTIZACIÓN", "note": "no se pudo validar el precio actual — verifica antes de operar"}
    elif lp <= z.get("sl", 0):
        st = {"icon": "⛔", "label": "ANULADA", "note": "el precio ya está bajo el stop — no operar"}
    elif lp > max_chase:
        st = {"icon": "🟠", "label": "LEJOS", "note": f"sobre ${max_chase}: deja la orden límite en ${entry}, no persigas"}
    elif lp > entry:
        st = {"icon": "🟡", "label": "CERCA", "note": f"orden límite en ${entry} (válida {a['reglas']['fill_window']} sesiones)"}
    else:
        st = {"icon": "🟢", "label": "EN ZONA", "note": "precio en o bajo la entrada — la orden límite se llenaría"}
    a["status"] = st
    return st


# ═══ CAPAS ═════════════════════════════════════════════════════
def evaluate(r, ctx):
    etf = is_etf_or_index(r)
    cs = composite_score(r)
    alba = r.get("alba") or {}
    res = {
        "ticker": r.get("ticker", "?"), "name": r.get("name", "?"), "price": r.get("close"),
        "sector": r.get("sector") or "N/A", "is_etf": etf, "composite": cs,
        "score": r.get("score"), "ai": r.get("ai"), "rsi": r.get("rsi"),
        "buffett": r.get("buffett"), "buffett_v": r.get("buffett_v", "⚪ SIN DATOS"),
        "mos": r.get("mos"), "rs_rank": r.get("rs_rank"), "earn_days": r.get("earn_days"),
        "earn_date": r.get("earn_date"), "asof": r.get("asof"), "fg": r.get("fg"),
        "setup": alba.get("setup"), "setup_desc": alba.get("desc"),
        "dist20_atr": alba.get("dist20_atr"), "atr_pct": alba.get("atr_pct"),
        "failed": [], "layers_passed": 0, "all_passed": False,
        "origen": r.get("origen") or "Universo principal",
    }
    # Capa 1 — TENDENCIA
    l1 = bool(alba.get("tendencia"))
    if not l1: res["failed"].append("Tendencia")
    # Capa 2 — CALIDAD
    if etf:
        l2 = True
    else:
        eq_clean = not (grade_score(r.get("eps_gr", "")) >= 4 and grade_score(r.get("roa_gr", "")) <= 2)
        roe, roa = r.get("roe") or 0, r.get("roa") or 0
        debt_ok = not (roe > 0 and roa > 0 and roe / roa > 3)
        l2 = cs >= 55 and (r.get("eps_g") or 0) > 0 and roe >= 8 and roa >= 3 and eq_clean and debt_ok
    if not l2: res["failed"].append("Calidad")
    # Capa 3 — SETUP de hoy
    setup = alba.get("setup")
    l3 = setup in ENABLED_SETUPS and alba.get("dias_desde_setup") == 0
    if not l3: res["failed"].append("Setup")
    # Capa 4 — RIESGO
    why = []
    if r.get("stale") or r.get("close") is None:
        why.append("dato desactualizado")
    if (ctx["session_ref"] and r.get("asof") and "." not in yf_symbol(res["ticker"])
            and r["asof"] != ctx["session_ref"]):
        why.append(f"vela {r.get('asof')} ≠ sesión {ctx['session_ref']}")
    ed = r.get("earn_days")
    if ed is not None and ed <= EARNINGS_BLACKOUT_DAYS:
        why.append(f"earnings en {ed}d")
    if ctx["regime"] == "NEUTRAL" and (r.get("rs_rank") is None or r["rs_rank"] < 60):
        why.append("RS < 60 en régimen neutral")
    if res["ticker"] in ctx["open_tickers"]:
        why.append("ya tiene una alerta abierta")
    price = r.get("close") or 0
    dv = r.get("dollar_vol_m")
    if dv is None and r.get("avg_vol_m") is not None and price:
        dv = r["avg_vol_m"] * price               # millones de acciones × precio
    if price and price < MIN_PRICE:
        why.append(f"precio < {MIN_PRICE:g} USD")
    if dv is not None and dv < MIN_DV:
        why.append(f"liquidez {dv:.1f} M USD/día < {MIN_DV:g}")
    if LEVERAGED.search(str(r.get("name") or "")):
        why.append("ETF apalancado o inverso")
    hab = (ctx["protocol"].get("habilitacion") or {}).get(setup) if setup else None
    if setup and ctx["protocol"] and hab is not None and not hab.get("expectativa_positiva"):
        why.append(f"{setup} sin expectativa positiva en el backtest")
    l4 = not why
    if not l4: res["failed"].append("Riesgo: " + ", ".join(why))
    res["layers_passed"] = sum([l1, l2, l3, l4])
    res["all_passed"] = l1 and l2 and l3 and l4
    # Niveles de la orden (bracket Alba) y estadística calibrada
    lv = alba.get("niveles") or {}
    if lv.get("entry"):
        res["zones"] = {"entry": lv["entry"], "sl": lv["sl"], "tp": lv["tp"],
                        "tp1": None, "tp2": lv["tp"], "atr": lv.get("atr")}
        risk = lv["entry"] - lv["sl"]
        if risk > 0:
            stop_pct = risk / lv["entry"] * 100
            res["sizing"] = {
                "stop_pct": round(stop_pct, 2),
                "objetivo_pct": round((lv["tp"] / lv["entry"] - 1) * 100, 2),
                "riesgo_pct_capital": RISK_PCT,
                "posicion_pct_capital": round(min(100.0, RISK_PCT / stop_pct * 100), 1),
                "acciones_por_10k": int((10000 * RISK_PCT / 100) / risk),
            }
    res["reglas"] = {"bracket": "ALBA 2/4", "fill_window": ap.BRACKET["fill_window"],
                     "expiry": ap.BRACKET["expiry"]}
    res["stats"] = build_stats(setup, hab, ctx)
    res["prob"] = res["stats"].get("p_tp") if res["stats"].get("calibrada") else None
    return res


def build_stats(setup, hab, ctx):
    st = {"calibrada": False}
    if hab and hab.get("n"):
        st.update({
            "calibrada": True, "fuente": f"backtest del protocolo ({ctx['protocol'].get('desde')} → {ctx['protocol'].get('hasta')})",
            "n": hab.get("n"), "p_tp": hab.get("p_tp"), "p_tp_ic95": hab.get("p_tp_ic95"),
            "acierto": hab.get("acierto"), "ret_medio": hab.get("ret_medio"),
            "ret_medio_oos": hab.get("ret_medio_oos"), "dias_medios": hab.get("dias_medios"),
            "le_gana_al_azar": hab.get("le_gana_al_azar"),
        })
    live = ((ctx["history"].get("summary") or {}).get("por_setup") or {}).get(setup or "")
    if live and live.get("n"):
        st["en_vivo"] = {k: live.get(k) for k in ("n", "acierto", "p_tp", "expectativa_pct")}
    return st


# ═══ MENSAJES ══════════════════════════════════════════════════
def fmt_stats(a):
    s = a.get("stats") or {}
    if not s.get("calibrada"):
        return "📊 Estadística: sin calibrar todavía (el backtest del protocolo aún no ha corrido)"
    ic = s.get("p_tp_ic95") or [None, None]
    txt = (f"📊 Histórico {a['setup']}: tocó el objetivo antes que el stop en {s['p_tp']}% "
           f"(IC95 {ic[0]}–{ic[1]}%, n={s['n']}) · resultado medio {s['ret_medio']:+.2f}% neto · ~{s.get('dias_medios')} sesiones")
    txt += "\n" + ("✅ Le gana a entrar al azar en tendencia" if s.get("le_gana_al_azar")
                   else "➖ No le gana a entrar al azar en tendencia: la ventaja viene del bracket y la tendencia, no del setup")
    if s.get("en_vivo"):
        v = s["en_vivo"]
        txt += f"\n📈 En vivo: {v['n']} cerradas · acierto {v['acierto']}% · expectativa {v['expectativa_pct']:+.2f}%"
    return txt


def build_telegram_msg(confirmed, watch, timestamp, regime_info=None, note=None):
    msg = f"🌅 *ALBA SCANNER PRO*\n{timestamp}\n"
    if regime_info:
        msg += f"{regime_info.get('icon','')} Régimen: *{regime_info.get('regime','')}* (SPY {regime_info.get('spy_vs_sma200_pct',0):+.1f}% vs SMA200)\n"
    msg += "━━━━━━━━━━━━━━━━━\n"
    msg += f"✅ *{len(confirmed)} ALERTA(S) 4/4*\n\n"
    for a in confirmed:
        z = a["zones"]; sz = a.get("sizing") or {}
        msg += f"🌅 *{a['ticker']}* — {a['setup']} · {a['sector']}" + (" · 🗂 Listado" if a.get("origen") == "Listado" else "") + "\n"
        msg += f"💰 Cierre {a['asof']}: ${a['price']}\n"
        msg += f"🎯 Orden LÍMITE: ${z['entry']} (válida {a['reglas']['fill_window']} sesiones desde mañana)\n"
        msg += f"🛑 Stop: ${z['sl']} (−{sz.get('stop_pct','?')}%) · 🏁 Objetivo: ${z['tp']} (+{sz.get('objetivo_pct','?')}%)\n"
        msg += f"⚖️ Riesgo {sz.get('riesgo_pct_capital', RISK_PCT)}% ⇒ posición ≈ {sz.get('posicion_pct_capital','?')}% del capital (≈{sz.get('acciones_por_10k','?')} acc. por cada $10k)\n"
        msg += fmt_stats(a) + "\n"
        if a.get("buffett") is not None:
            msg += f"🏰 Calidad: {a.get('buffett_v','')} ({a['buffett']}/100)\n"
        if a.get("rs_rank") is not None:
            msg += f"📈 Fuerza relativa: percentil {a['rs_rank']}\n"
        if a.get("earn_days") is not None and a["earn_days"] <= 20:
            msg += f"📅 Earnings en {a['earn_days']} días ({a.get('earn_date','')})\n"
        st = a.get("status")
        if st:
            msg += f"{st['icon']} *{st['label']}*: {st['note']}\n"
        msg += "📋 Sin salida parcial: el stop no se mueve; se cierra en objetivo, stop o a las 45 sesiones.\n\n"
    if watch:
        msg += "⏳ *EN OBSERVACIÓN (3/4):*\n"
        for a in watch[:5]:
            msg += f"  • {a['ticker']} {a.get('setup') or ''} — falta: {', '.join(a['failed'])}\n"
    if note:
        msg += f"\nℹ️ {note}\n"
    msg += "\n⚠️ Información educativa, no es consejo financiero."
    return msg


def build_email_html(confirmed, watch, timestamp, regime_info=None):
    html = f"""<html><body style="margin:0;padding:0;background:#0b0d12;font-family:'Segoe UI',Arial,sans-serif;color:#d6d8de">
    <div style="max-width:640px;margin:0 auto;padding:20px">
    <div style="background:#141820;border:1px solid #2a2f3a;border-radius:10px;padding:18px;margin-bottom:14px;text-align:center">
      <h1 style="color:#ffb74d;margin:0;font-size:22px;letter-spacing:2px">🌅 ALBA SCANNER PRO</h1>
      <p style="color:#8a90a0;margin:6px 0 0;font-size:12px">{timestamp}</p>
      <p style="color:#ffb74d;margin:10px 0 0;font-size:15px;font-weight:bold">{len(confirmed)} alerta(s) 4/4 · Tendencia ✓ Calidad ✓ Setup ✓ Riesgo ✓</p>
    </div>"""
    for a in confirmed:
        z = a["zones"]; sz = a.get("sizing") or {}
        stats = fmt_stats(a).replace("\n", "<br>")
        st = a.get("status") or {}
        html += f"""
    <div style="background:#141820;border:1px solid #ffb74d55;border-left:4px solid #ffb74d;border-radius:10px;padding:16px;margin-bottom:12px">
      <div style="font-size:18px;font-weight:bold;color:#ffb74d">{a['ticker']} — {a['name']}</div>
      <div style="font-size:11px;color:#8a90a0;margin-top:3px">{a['setup']} · {a['sector']} · cierre {a['asof']} ${a['price']}{' · origen: Listado completo' if a.get('origen') == 'Listado' else ''}</div>
      <div style="font-size:11px;color:#b0b6c4;margin-top:6px">{a.get('setup_desc') or ''}</div>
      <table style="width:100%;border-collapse:separate;border-spacing:4px;margin-top:10px"><tr>
        <td style="padding:8px;background:#0f1218;border-radius:6px;text-align:center"><div style="font-size:9px;color:#6b7080">ORDEN LÍMITE</div><div style="font-size:15px;font-weight:bold;color:#e6e8ee">${z['entry']}</div></td>
        <td style="padding:8px;background:#0f1218;border-radius:6px;text-align:center"><div style="font-size:9px;color:#6b7080">STOP</div><div style="font-size:15px;font-weight:bold;color:#ff6b6b">${z['sl']}</div></td>
        <td style="padding:8px;background:#0f1218;border-radius:6px;text-align:center"><div style="font-size:9px;color:#6b7080">OBJETIVO</div><div style="font-size:15px;font-weight:bold;color:#4cd08a">${z['tp']}</div></td>
        <td style="padding:8px;background:#0f1218;border-radius:6px;text-align:center"><div style="font-size:9px;color:#6b7080">POSICIÓN (riesgo {sz.get('riesgo_pct_capital', RISK_PCT)}%)</div><div style="font-size:15px;font-weight:bold;color:#e6e8ee">{sz.get('posicion_pct_capital','?')}%</div></td>
      </tr></table>
      <div style="margin-top:10px;font-size:11px;color:#b0b6c4;line-height:1.5">{stats}</div>
      <div style="margin-top:8px;font-size:11px;color:#ffb74d">{st.get('icon','')} {st.get('label','')} {('— ' + st.get('note','')) if st else ''}</div>
    </div>"""
    if watch:
        html += '<div style="background:#141820;border:1px solid #2a2f3a;border-radius:10px;padding:14px"><p style="color:#8a90a0;font-size:12px;font-weight:bold;margin:0 0 8px">En observación (3/4)</p>'
        for a in watch[:8]:
            html += f'<div style="padding:3px 0;font-size:11px"><b style="color:#d6d8de">{a["ticker"]}</b> <span style="color:#8a90a0">{a.get("setup") or ""} — falta: {", ".join(a["failed"])}</span></div>'
        html += "</div>"
    html += """<p style="text-align:center;color:#6b7080;font-size:10px;margin-top:16px">Alba Scanner Pro · solo LONG · Información educativa, no es consejo financiero.</p></div></body></html>"""
    return html


def send_telegram(message, token, chat_id):
    try:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        data = json.dumps({"chat_id": chat_id, "text": message, "parse_mode": "Markdown"}).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
        resp = urllib.request.urlopen(req, timeout=15)
        print(f"  {'✅' if resp.status == 200 else '⚠️'} Telegram ({resp.status})")
    except Exception as e:
        print(f"  ❌ Telegram error: {e}")


def send_email(confirmed, watch, to_email, smtp_user, smtp_pass, timestamp, regime_info):
    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"🌅 Alba: {', '.join(a['ticker'] for a in confirmed)} — {len(confirmed)} alerta(s)"
    msg["From"] = smtp_user; msg["To"] = to_email
    msg.attach(MIMEText(build_telegram_msg(confirmed, watch, timestamp, regime_info), "plain", "utf-8"))
    msg.attach(MIMEText(build_email_html(confirmed, watch, timestamp, regime_info), "html", "utf-8"))
    server = smtplib.SMTP("smtp.gmail.com", 587); server.starttls()
    server.login(smtp_user, smtp_pass); server.sendmail(smtp_user, to_email, msg.as_string()); server.quit()
    print(f"  ✅ Email enviado a {to_email}")


# ═══ MAIN ══════════════════════════════════════════════════════
def write_empty(timestamp, regime_info, note):
    save("alerts.json", {"checked_at": timestamp, "regime": regime_info, "confirmed": 0,
                         "signals": [], "watchlist": [], "note": note})


def main():
    snapshot = load("snapshot.json")
    if not snapshot:
        print("ERROR: snapshot.json no existe."); sys.exit(1)
    timestamp = datetime.now(BOGOTA).strftime("%Y-%m-%d %H:%M:%S") + " (Hora Colombia)"
    print(f"ALBA SCANNER PRO — Alertas · {timestamp}\n{'=' * 55}")
    regime_info = snapshot.get("market_regime") or {}
    regime = regime_info.get("regime", "NEUTRAL")
    health = load("health.json", {}) or {}

    # ── Datos sanos o nada ──
    if health.get("status") == "FAILED":
        note = (f"Sin alertas: la actualización de datos falló la guarda de salud "
                f"({health.get('pct_problemas')}% del universo sin la vela {health.get('session_ref')}). "
                "La corrida de respaldo lo repetirá.")
        print("  ⛔ " + note)
        write_empty(timestamp, regime_info, note)
        return
    print(f"  {regime_info.get('icon','🟡')} Régimen: {regime} — {regime_info.get('advice','')}")
    if regime == "BEAR":
        note = "Alertas de compra suspendidas: SPY bajo su SMA200 (régimen bajista)."
        print("  🔴 " + note)
        write_empty(timestamp, regime_info, note)
        return

    history = load("alerts_history.json", {"alerts": []}) or {"alerts": []}
    open_hist = [a for a in history.get("alerts", []) if a.get("status") in OPEN_STATES]
    protocol = load("protocol_bt.json", {}) or {}
    ctx = {
        "regime": regime, "session_ref": snapshot.get("session_ref"),
        "open_tickers": {a["ticker"] for a in open_hist},
        "protocol": protocol, "history": history,
    }
    if not protocol:
        print("  ℹ️ protocol_bt.json aún no existe: los setups se alertan como 'sin calibrar'.")

    uniq = {}
    for gn, rows in snapshot.get("groups", {}).items():
        for r in rows:
            uniq.setdefault(r.get("ticker"), r)
    # Candidatos del Listado completo (solo los que hoy tienen setup y pasaron filtros)
    listado = load("listado_alba.json", {}) or {}
    n_list = 0
    if listado.get("session_ref") in (None, ctx["session_ref"]):
        for r in listado.get("rows", []):
            if r.get("ticker") and r["ticker"] not in uniq:
                uniq[r["ticker"]] = r; n_list += 1
    print(f"  Universo evaluado: {len(uniq) - n_list} del snapshot + {n_list} candidatos del Listado completo "
          f"({listado.get('setups_listado', 0)} setups encontrados en ~11.500 símbolos)")
    candidates, watch = [], []
    for r in uniq.values():
        res = evaluate(r, ctx)
        if res["all_passed"] and res.get("zones"):
            candidates.append(res)
        elif res["layers_passed"] == 3 and res.get("setup"):
            watch.append(res)

    # ── Ranking y topes (diversificación) ──
    prio = {s: i for i, s in enumerate(ap.SETUP_PRIORITY)}
    candidates.sort(key=lambda a: (prio.get(a["setup"], 9), -(a.get("buffett") or 0), -(a.get("rs_rank") or 0)))
    sector_open = {}
    for a in open_hist:
        sec = a.get("sector") or "N/A"
        sector_open[sec] = sector_open.get(sec, 0) + 1
    confirmed = []
    for a in candidates:
        sec = a["sector"]
        if sector_open.get(sec, 0) >= MAX_PER_SECTOR:
            a["failed"].append(f"Riesgo: tope de {MAX_PER_SECTOR} posiciones en {sec}")
            watch.append(a); continue
        if len(confirmed) >= MAX_NEW_PER_DAY:
            a["failed"].append(f"Riesgo: tope de {MAX_NEW_PER_DAY} alertas nuevas por día")
            watch.append(a); continue
        confirmed.append(a)
        sector_open[sec] = sector_open.get(sec, 0) + 1
    watch.sort(key=lambda a: (prio.get(a.get("setup"), 9), -(a.get("composite") or 0)))
    print(f"\n{'=' * 55}\nRESULTADO: {len(confirmed)} alertas 4/4 | {len(watch)} en observación")
    for a in confirmed:
        z = a["zones"]
        print(f"  🌅 {a['ticker']} {a['setup']} · límite ${z['entry']} · SL ${z['sl']} · TP ${z['tp']} · "
              f"P(TP) hist {a['stats'].get('p_tp', 's/c')}%")

    # ── Deduplicación diaria ──
    today = datetime.now(BOGOTA).strftime("%Y-%m-%d")
    state = load("alerts_state.json", {}) or {}
    already = set(state.get(today, []))
    new_signals = [a for a in confirmed if a["ticker"] not in already]
    save("alerts_state.json", {today: sorted(already | {a["ticker"] for a in confirmed})})

    if new_signals:
        print("  ⏱ Validando precio actual...")
        for a in new_signals:
            st = classify_freshness(a)
            if st:
                print(f"    {a['ticker']}: ahora ${a.get('live','?')} → {st['icon']} {st['label']}")

    save("alerts.json", {
        "checked_at": timestamp, "regime": regime_info, "confirmed": len(confirmed),
        "session_ref": ctx["session_ref"],
        "reglas": {"bracket": "ALBA 2/4", "max_nuevas": MAX_NEW_PER_DAY, "max_sector": MAX_PER_SECTOR,
                   "riesgo_pct": RISK_PCT, "setups": ENABLED_SETUPS},
        "signals": [{
            "ticker": a["ticker"], "name": a["name"], "sector": a["sector"], "setup": a["setup"],
            "origen": a.get("origen"),
            "setup_desc": a.get("setup_desc"), "composite": a["composite"], "prob": a.get("prob"),
            "stats": a["stats"], "sizing": a.get("sizing"), "reglas": a["reglas"],
            "fg": a.get("fg"), "buffett": a.get("buffett"), "mos": a.get("mos"), "rs_rank": a.get("rs_rank"),
            "asof": a.get("asof"), "price": a.get("price"), "live": a.get("live"), "status": a.get("status"),
            "max_chase": a.get("max_chase"), "zones": a["zones"],
        } for a in confirmed],
        "watchlist": [{"ticker": a["ticker"], "setup": a.get("setup"), "origen": a.get("origen"),
                       "failed": a["failed"]} for a in watch[:25]],
        "universo": {"snapshot": len(uniq) - n_list, "listado_candidatos": n_list,
                     "listado_setups": listado.get("setups_listado"),
                     "listado_cobertura_pct": listado.get("cobertura_pct")},
    })

    if not new_signals:
        print("  ℹ️ Nada nuevo que notificar.")
        return
    smtp_user, smtp_pass = os.environ.get("SMTP_USER", ""), os.environ.get("SMTP_PASS", "")
    to_email = os.environ.get("ALERT_EMAIL", "")
    tg_token, tg_chat = os.environ.get("TELEGRAM_TOKEN", ""), os.environ.get("TELEGRAM_CHAT_ID", "")
    if smtp_user and smtp_pass and to_email:
        try: send_email(new_signals, watch, to_email, smtp_user, smtp_pass, timestamp, regime_info)
        except Exception as e: print(f"  ❌ Email error: {e}")
    else:
        print("  ⚠️ Email no configurado (SMTP_USER, SMTP_PASS, ALERT_EMAIL).")
    if tg_token and tg_chat:
        try: send_telegram(build_telegram_msg(new_signals, watch, timestamp, regime_info), tg_token, tg_chat)
        except Exception as e: print(f"  ❌ Telegram error: {e}")
    else:
        print("  ⚠️ Telegram no configurado (TELEGRAM_TOKEN, TELEGRAM_CHAT_ID).")


if __name__ == "__main__":
    main()
