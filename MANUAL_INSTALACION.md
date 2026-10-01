# 📦 Manual de Instalación — Alba Scanner Pro v1.0

Alba es un proyecto **nuevo e independiente**: no reemplaza a FigAnd. Puedes tener
los dos repositorios funcionando a la vez. La forma recomendada es
**GitHub Pages + GitHub Actions** (se actualiza solo, sin servidor).

## Requisitos

- Cuenta de GitHub (el repositorio debe ser **público** para GitHub Pages gratis).
- Opcional: Gmail (alertas por correo), un bot de Telegram, API key gratis de Finnhub.
- Para probar en tu PC: Python 3.10+ (recomendado 3.12).

---

## Opción A — GitHub Pages + Actions (recomendada)

### Paso 1 — Crear el repositorio

1. En GitHub: **New repository** → nombre sugerido `Alba-Scanner-Pro` → Public → *Create*.
2. Descomprime `Alba-Scanner-Pro.zip` en tu PC.

### Paso 2 — Subir los archivos

**Forma más fácil (GitHub Desktop):** *File → Add local repository* (o *Clone* el
repo vacío), copia dentro todo el contenido de la carpeta `alba-scanner-pro`,
escribe un mensaje ("Alba v1.0") → **Commit to main** → **Push origin**.
GitHub Desktop sí sube la carpeta oculta `.github`.

**Desde la web (arrastrar y soltar):** arrastra todos los archivos y carpetas
**excepto `.github`** (el navegador suele ignorar las carpetas que empiezan con
punto). Después crea los dos workflows a mano:

1. En el repo: **Add file → Create new file**.
2. En el nombre escribe exactamente `.github/workflows/refresh_data.yml`
   (al escribir `/` GitHub crea las carpetas).
3. Abre el archivo `refresh_data.yml` del zip con el Bloc de notas, copia todo y pégalo.
4. **Commit changes**.
5. Repite con `.github/workflows/seguimiento.yml`.

Comprueba en la pestaña **Actions** que aparecen *"Alba — Actualización diaria
(cierre + respaldo)"* y *"Alba — Seguimiento intradía del historial"*.

### Paso 3 — Permisos de Actions

*Settings → Actions → General → Workflow permissions* → **Read and write
permissions** → *Save*. Sin esto los workflows no pueden guardar los datos.

### Paso 4 — GitHub Pages

*Settings → Pages* → *Source: Deploy from a branch* → rama `main`, carpeta
`/ (root)` → *Save*. En 1–2 minutos: `https://TU_USUARIO.github.io/Alba-Scanner-Pro/`.

### Paso 5 — Secrets de alertas (opcional)

*Settings → Secrets and variables → Actions → New repository secret*:

| Secret | Qué es |
|---|---|
| `SMTP_USER` | Tu Gmail (ej. `tucorreo@gmail.com`) |
| `SMTP_PASS` | **Contraseña de aplicación** de Google (16 caracteres; requiere verificación en 2 pasos) |
| `ALERT_EMAIL` | Correo que recibe las alertas |
| `TELEGRAM_TOKEN` | Token del bot (@BotFather → `/newbot`) |
| `TELEGRAM_CHAT_ID` | Tu chat ID numérico (@userinfobot) |
| `FINNHUB_KEY` | Opcional: segunda fuente para reconstruir velas faltantes |

Si ya los tenías en FigAnd, créalos igual en este repo nuevo (los secrets no se comparten entre repositorios).

### Paso 6 — Primera ejecución

*Actions → Alba — Actualización diaria → Run workflow* (deja "forzar" en `no`).

La corrida revisa **dos universos**, cada uno con la profundidad que permite el tiempo:

| Universo | Cuántos | Qué se hace |
|---|---|---|
| Principal (los grupos del Radar) | ~1.170 tickers | 5 años de velas, fundamentales, calidad Buffett, setups Alba, backtest del protocolo |
| Listado completo (`universe.json`) | ~11.500 símbolos | 2 años de velas por lotes: perfiles COMBO y setups Alba. Solo los que **hoy** tienen setup, son líquidos (≥ 5 USD y ≥ 5 M USD/día), no son ETF apalancados y están en tendencia reciben fundamentales (máx. 150 por día) |

Los dos alimentan las mismas alertas con las mismas 4 capas. Pedir
fundamentales a los 11.500 tomaría horas; por eso solo se piden a los pocos que
tienen setup ese día.

La primera vez tarda entre 60 y 100 minutos (la mitad es el universo principal,
unos 30 min el Listado y, si es viernes o no existe, el backtest clásico).
Al terminar tendrás en `data/`: `snapshot.json`, `health.json`,
`protocol_bt.json`, `figand_scan.json`, `listado_alba.json`, `alerts.json`,
`alerts_history.json` y `backtest.json`.

Desde ahí todo es automático:

| Qué | Cuándo (hora de Colombia) |
|---|---|
| Actualización del cierre + Listado + alertas | ~15:20 (verano de EEUU) o ~16:20 (invierno), lunes a viernes; tarda ~60–90 min |
| Respaldo, solo si la noche falló | ~06:17 de martes a sábado |
| Seguimiento intradía del historial | ~10:05 y ~13:05 |

GitHub puede retrasar los horarios programados entre 10 y 60 minutos; es normal.

### Paso 7 — App en el celular

Abre `https://TU_USUARIO.github.io/Alba-Scanner-Pro/movil.html` en Safari →
Compartir → **Agregar a inicio**. Aparece con el ícono del amanecer. (Detalle en
`MANUAL_APP_IPHONE.md`.)

---

## Opción B — Probar en tu PC

```bash
cd alba-scanner-pro
python -m venv venv
venv\Scripts\activate            # Windows  (Mac/Linux: source venv/bin/activate)
pip install -r requirements.txt

python scripts/build_data.py --out-dir data            # completo (30–60 min)
python scripts/build_data.py --out-dir data --quick    # prueba rápida (solo core, sin backtests)
python scripts/check_alerts.py                          # alertas en consola
python scripts/track_alerts.py                          # historial
python -m http.server 8000                              # abre http://localhost:8000
```

---

## Verificar que todo está sano

- En el dashboard, junto al logo: **🩺 Datos OK · x%**. Si ves **⛔ Datos
  incompletos**, la corrida de respaldo lo repetirá sola; no hay alertas mientras tanto.
- En *Actions*, el paso **"¿Toca correr?"** explica por qué una corrida programada
  corrió o se saltó (por ejemplo "la sesión 2026-09-24 ya está publicada y sana").
- La pestaña **🌅 Alba** muestra la fecha de la vela de referencia y cuántas velas
  se reconstruyeron.

## Problemas frecuentes

**El workflow no aparece en Actions** → falta la carpeta `.github/workflows`
(ver Paso 2, "Desde la web").

**"permission denied" al hacer push** → falta el Paso 3.

**"⛔ Más del 5% del universo sin la vela…"** → Yahoo entregó datos incompletos.
El snapshot anterior se conserva y el respaldo de la mañana lo repite. Si
necesitas publicar de todas formas: *Run workflow* con `forzar = si` (no recomendado).

**El correo no llega** → `SMTP_PASS` debe ser contraseña de aplicación; revisa el
log del paso "Alertas Alba".

**Telegram no envía** → escríbele `/start` a tu bot primero y usa el chat ID numérico.

**El repositorio crece mucho** → el backtest clásico (`backtest.json`, ~40 MB) se
recalcula solo los viernes. Si quieres desactivarlo: variable `LEGACY_BACKTEST=never`.
