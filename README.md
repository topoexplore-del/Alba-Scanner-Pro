# 🌅 Alba Scanner Pro

**Scanner de acciones LONG-only con un protocolo que se puede medir.**
Alba nace de la auditoría de FigAnd Scanner Pro (septiembre 2026): conserva todo
lo que funcionaba (Radar, Screener, COMBO, Analysis, fichas, app móvil, Historial)
y corrige lo que producía malas entradas.

> El nombre: *el alba es el inicio del día*. El objetivo del sistema es entrar al
> **inicio** del movimiento, no cuando ya está estirado.

---

## Qué cambió frente a FigAnd

| Problema en FigAnd | Qué hace Alba |
|---|---|
| 6 de 11 cierres publicados con 25–98% del universo **sin precio** (velas vacías de Yahoo después de las 00:00 UTC) | Limpia toda descarga, **reconstruye la vela faltante** desde velas de 30 min (o Finnhub), y **no publica** el snapshot si más del 5% queda sin la sesión de referencia. Corrida de **respaldo** a las 06:17 ET si la noche falló. |
| La corrida nocturna arrancaba tarde y cruzaba la medianoche UTC | Dos horarios de cierre (verano/invierno) con una **compuerta** que solo deja correr el que corresponde, y sin duplicados. |
| El historial contaba **fills imposibles** (36 de 48 en la vela de la propia señal) | El seguimiento usa **exactamente** las reglas del backtest: fill solo desde la sesión siguiente, gaps reales, SL gana empates, resultado neto de costos. Las 49 alertas de FigAnd se re-evalúan. |
| "Probabilidad" de **95%** en 44 de 49 alertas, EV con un pago inexistente, Kelly de 92% | Se muestra la **frecuencia histórica real** del setup (objetivo antes que stop) con su intervalo de confianza, medida en el backtest del protocolo real. |
| Las alertas compraban **tarde** (a 1,4% del máximo anual, RSI 62) | Tres setups medibles de **inicio de movimiento** (RETROCESO a la EMA20, RUPTURA de base, IMPULSO con filtro anti-extensión) evaluados en la vela de hoy. |
| Bracket 1,5/2 ATR; recomendación de TP1 parcial + stop a entrada | Datos de 4 años: la salida parcial con breakeven fue **la peor**. Alba usa **stop −2 ATR / objetivo +4 ATR**, sin parcial (R/R 1:2). |
| 19 de 37 operaciones en un solo sector; misma acción alertada 3–4 veces | **Una alerta abierta por ticker**, máximo **2 por sector** y **5 nuevas por día**. |
| El backtest medía cierre a cierre a plazo fijo (58–69% de "acierto") | **Backtest del protocolo real** diario, comparado contra **entradas al azar** con el mismo bracket y separado dentro/fuera de muestra. |
| COMBO: P2 y P3 eran las mismas 14 operaciones; P4 mal traducido del Excel | P3 fusionado con P2; P4 desactivado (requiere velas de 1 hora). COMBO queda **en observación**. |
| Tres juegos de zonas distintos según la pestaña | Un solo bracket (el de las alertas) en Radar, Entry Zones, Game Theory, móvil y correo. |
| Markov, Laplace y Game Theory mostraban "probabilidades" de coeficientes fijos | Se conservan como contexto, marcadas como **ilustrativas**. |

**Universo:** análisis completo de ~1.170 tickers (grupos del Radar) y setups
Alba en los ~11.500 símbolos del Listado; a estos últimos solo se les piden
fundamentales si hoy tienen setup y son líquidos. Ambos pasan por las mismas 4 capas.

El detalle, la evidencia y cómo operar: **[MANUAL_ALBA.md](MANUAL_ALBA.md)**.
Instalación paso a paso: **[MANUAL_INSTALACION.md](MANUAL_INSTALACION.md)**.

---

## Estructura

```
alba-scanner-pro/
├── index.html              Dashboard (pestaña nueva 🌅 Alba)
├── movil.html              App móvil (PWA, instalable en iPhone/Android)
├── figand_engine.js        Motor COMBO (perfiles del Excel)
├── scripts/
│   ├── alba_protocol.py    ← NUEVO: indicadores, setups, bracket y simulador (una sola fuente de verdad)
│   ├── protocol_bt.py      ← NUEVO: backtest del protocolo real vs. azar
│   ├── market_calendar.py  ← NUEVO: sesiones y festivos NYSE 2026–2027
│   ├── run_gate.py         ← NUEVO: compuerta de las corridas programadas
│   ├── alba_listado.py     ← NUEVO: fundamentales solo para los candidatos del Listado con setup hoy
│   ├── build_data.py       Pipeline de datos (con limpieza, reparación y guarda de salud)
│   ├── check_alerts.py     Alertas Alba (4 capas medibles)
│   ├── track_alerts.py     Seguimiento con las reglas del backtest
│   ├── figand_scan.py      Escaneo del Listado completo (~11.500): COMBO + setups Alba
│   └── figand_stats.py     Perfiles COMBO
├── data/                   JSON publicados (snapshot, health, alerts, protocol_bt, historial…)
└── .github/workflows/
    ├── refresh_data.yml    Actualización diaria + respaldo
    └── seguimiento.yml     Seguimiento intradía del historial
```

## Inicio rápido

```bash
pip install -r requirements.txt
python scripts/build_data.py --out-dir data      # datos + backtest del protocolo
python scripts/check_alerts.py                    # alertas (en consola si no hay secrets)
python scripts/track_alerts.py                    # historial
python -m http.server 8000                        # abre http://localhost:8000
```

⚠️ Información educativa. No es asesoría financiera ni recomendación de inversión.
