"""
ALBA — Compuerta de la corrida programada.
Evita corridas duplicadas y dispara el respaldo matutino SOLO si la
actualización de la noche no quedó sana. Escribe run=true/false en
$GITHUB_OUTPUT.

  · Manual (workflow_dispatch) → siempre corre.
  · Noche (20:20 y 21:20 UTC) → corre si la sesión de hoy ya cerró y
    todavía no hay una actualización completa y sana de esa sesión.
    (Dos horarios porque GitHub usa UTC y EEUU cambia de hora.)
  · Respaldo (11:17 UTC) → corre si la última actualización sana es
    anterior a la última sesión cerrada.
"""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from market_calendar import now_et, expected_session_date, is_trading_day, CLOSE_MINUTES

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MORNING = "17 11 * * 2-6"


def decide():
    event = os.environ.get("EVENT", "")
    sched = os.environ.get("SCHEDULE", "")
    now = now_et()
    exp = str(expected_session_date(now))
    try:
        h = json.load(open(os.path.join(BASE, "data", "health.json"), encoding="utf-8"))
    except Exception:
        h = {}
    last_ok = (h.get("ultimo_full_ok") or {}).get("session_ref")
    if event != "schedule":
        return True, "corrida manual"
    if sched == MORNING:
        if last_ok is None or last_ok < exp:
            return True, f"respaldo: última actualización sana {last_ok}, falta la sesión {exp}"
        return False, f"respaldo innecesario: la sesión {exp} ya está publicada"
    today = now.date()
    if not is_trading_day(today):
        return False, "hoy no hubo sesión (fin de semana o festivo)"
    if now.hour * 60 + now.minute < CLOSE_MINUTES:
        return False, "la sesión sigue abierta en EEUU (horario de invierno): corre la del siguiente horario"
    if last_ok == str(today):
        return False, f"la sesión {today} ya está publicada y sana"
    return True, f"cierre de la sesión {today}"


if __name__ == "__main__":
    run, why = decide()
    print(f"¿Correr? {'SÍ' if run else 'NO'} — {why}")
    out = os.environ.get("GITHUB_OUTPUT")
    if out:
        with open(out, "a") as f:
            f.write(f"run={'true' if run else 'false'}\n")
