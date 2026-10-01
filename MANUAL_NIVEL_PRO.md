# 🎓 Alba Scanner Pro — Manual del Nivel Profesional

> En Alba el backtest principal es el **del protocolo real** (pestaña 🌅 Alba, ver MANUAL_ALBA.md). El backtest clásico descrito aquí se conserva y se recalcula los viernes.

El sistema incorpora dos mejoras de grado profesional sobre el sistema base: **backtest de rigor institucional** y **conciencia de eventos (earnings)**. Este manual explica qué cambió, cómo leerlo y cómo configurarlo.

## Mejora 1 — Backtest de rigor institucional

### Costos de transacción

Todo P&L del backtest ahora se reporta en dos versiones: **bruto** (`avg_pnl`) y **neto** (`avg_pnl_net`), donde el neto descuenta 0.2% por operación de ida y vuelta (comisión + slippage, un supuesto conservador para acciones líquidas de EEUU). Es configurable con la variable de entorno `BACKTEST_COST_PCT` (en los workflows o localmente: `BACKTEST_COST_PCT=0.3 python scripts/build_data.py`). Por qué importa: una estrategia con edge bruto de +0.5% por operación y muchas señales puede ser perdedora neta — los costos son el impuesto silencioso que mata la mayoría de estrategias activas.

### Walk-forward (in-sample vs out-of-sample)

Cada estrategia reporta ahora un bloque `wf`: el win-rate en el primer **60% del histórico** (`wr_is`, in-sample) y en el **40% final** (`wr_oos`, out-of-sample). La lectura profesional: si una estrategia gana 70% in-sample pero 48% out-of-sample, está **sobreajustada** — memorizó el pasado en vez de capturar un patrón real. El número en el que debes basar decisiones es siempre el OOS. En la app móvil, la columna "OOS" de la pestaña Backtest muestra esto directamente.

### Métricas profesionales

Cada estrategia incluye además: **Sharpe por operación** (`sharpe_trade`: retorno neto medio dividido por su desviación — permite comparar estrategias con distinta frecuencia; >0.3 por trade es respetable), **máximo drawdown de la curva** (`max_dd`: la peor racha acumulada de la estrategia — te dice cuánto dolor habrías soportado), **expectancy neta** (lo que ganas en promedio por operación tras costos) y el **profit factor** sobre P&L neto.

### Benchmark: el listón

El `backtest.json` incluye ahora `meta.benchmark`: el retorno total, CAGR y máximo drawdown de **comprar SPY y no hacer nada** en la misma ventana (~5 años de datos, ampliada desde 2). La app lo muestra arriba de la pestaña Backtest. La regla profesional es brutal y simple: si una estrategia no supera al SPY pasivo después de costos, no merece tu capital — y la mayoría no lo hace. Este sistema te lo dice de frente en vez de ocultarlo.

### Histórico ampliado a 5 años

El backtest ahora cubre ~5 años (antes 2), lo que incluye el mercado bajista de 2022 — indispensable para que el filtro de régimen y el walk-forward signifiquen algo. Una estrategia probada solo en años alcistas no está probada.

## Mejora 2 — Conciencia de eventos (earnings y dividendos)

### Qué hace

Cada ticker ahora trae `earn_days` y `earn_date` (días hasta el próximo reporte de resultados) y `exdiv_date` (próxima fecha ex-dividendo) obtenidos del calendario de Yahoo. Se ven así:

- **Dashboard**: un marcador 📅 ámbar junto al ticker cuando los earnings están a 7 días o menos.
- **App móvil**: badge "📅E-Xd" en la tarjeta del ticker y campos explícitos en la ficha de detalle.
- **Alertas**: si la señal pasa las 4 capas pero los earnings están a **5 días o menos**, la alerta se **suprime** y el ticker pasa a la watchlist con la razón "Earnings en Xd (blackout)". Si están entre 6 y 14 días, la alerta se envía pero con una advertencia explícita "📅 ATENCIÓN: earnings en X días".

### Por qué

Comprar dos días antes de un reporte de resultados convierte una señal técnica en una moneda al aire con gaps del 5-10%: el resultado depende del reporte, no de tu análisis. Los profesionales no necesariamente evitan los earnings — pero jamás los ignoran, y nunca dejan que un sistema automático les compre a ciegas en esa ventana.

### Configuración

La ventana de blackout es configurable con `EARNINGS_BLACKOUT_DAYS` (por defecto 5). Para cambiarla en los workflows, añade en el paso "Check alerts":

```yaml
        env:
          EARNINGS_BLACKOUT_DAYS: '7'
```

Nota honesta: el calendario de earnings de Yahoo es gratuito y generalmente correcto, pero ocasionalmente trae fechas tentativas o ausentes para empresas pequeñas o extranjeras. Si un ticker no muestra fecha, el blackout simplemente no aplica para él — verifica manualmente antes de operar señales en temporada de resultados (enero, abril, julio, octubre).

## Cómo verificar que todo funciona

Tras la primera build completa (`python scripts/build_data.py --out-dir data` o el workflow Full Refresh, que ahora tarda algo más por los 5 años de histórico), revisa: en `backtest.json` el bloque `meta.benchmark` y, en cualquier ticker, los campos `avg_pnl_net`, `sharpe_trade`, `max_dd` y `wf`; en `snapshot.json`, los campos `earn_days`/`earn_date` en tickers con earnings próximos; y en la app móvil, las columnas Neto y OOS en Backtest y los badges 📅.

⚠️ Recordatorio: ni el mejor backtest garantiza resultados futuros. Estas mejoras no hacen al sistema infalible — lo hacen honesto.
