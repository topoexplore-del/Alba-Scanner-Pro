# 🌅 Manual de Alba — el protocolo, la evidencia y cómo operarlo

Este manual explica qué hace Alba, por qué se diseñó así, qué dicen los datos y
cómo usarlo sin engañarse. Léelo completo una vez; después basta con la sección
**"Cómo se opera una alerta"**.

---

## 1. La idea en una frase

Alba solo alerta cuando **los datos del día están completos**, la acción está en
**tendencia alcista**, tiene **calidad** fundamental, cerró hoy con un **setup de
inicio de movimiento**, y abrir la posición no rompe los **límites de riesgo**.
Lo que muestra como probabilidad es la **frecuencia real medida** en un backtest
que simula exactamente la operación, no una fórmula.

---

## 2. Qué acciones revisa

| Universo | Cuántos | Profundidad |
|---|---|---|
| **Principal** (grupos del Radar) | ~1.170 | Análisis completo: 5 años de velas, fundamentales, Buffett, setups, backtest |
| **Listado completo** (`universe.json`) | ~11.500 | Setups Alba con 2 años de velas por lotes; fundamentales **solo** para los que hoy tienen setup y pasan los filtros baratos (máx. 150/día) |

Filtros previos del Listado: no estar ya en el universo principal, precio ≥ 5 USD,
volumen promedio ≥ 5 millones de USD/día (20 sesiones), no ser ETF apalancado o
inverso, estar en tendencia y no tener una alerta abierta. Luego pasan por las
mismas cuatro capas; en la alerta aparecen con la etiqueta 🗂 **Listado**. Las
estadísticas del setup vienen del backtest del universo principal (mismas reglas).

Si el escaneo del Listado no alcanza a cubrirlo todo en su tiempo (30 min), la
siguiente corrida continúa donde quedó; la pestaña 🌅 Alba muestra la cobertura.

---

## 3. Las cuatro capas de una alerta

| Capa | Qué exige | Por qué |
|---|---|---|
| 1. **Tendencia** | Precio > SMA200, SMA50 > SMA200 y EMA20 > SMA50 | Solo LONG a favor de la tendencia mayor |
| 2. **Calidad** | Composite ≥ 55, EPS creciendo, ROE ≥ 8%, ROA ≥ 3%, sin señales de deuda/beneficio inflado (los ETF la omiten) | Filtro de negocio, igual que en FigAnd |
| 3. **Setup** | RETROCESO, RUPTURA o IMPULSO **en la vela de hoy** | El momento de entrada, medible |
| 4. **Riesgo** | Datos sanos · régimen no bajista · sin earnings en 5 días · RS ≥ 60 si el régimen es neutral · liquidez (≥ 5 USD y ≥ 5 M USD/día, sin ETF apalancados) · sin otra alerta abierta del mismo ticker · máx. 2 abiertas por sector · máx. 5 nuevas por día · el setup tiene expectativa positiva en el backtest | Evita las pérdidas en racimo que tuvo FigAnd (17 stops en Energía) |

Si falta una sola capa, el ticker queda **en observación** (el correo y el
dashboard dicen cuál capa falló).

### Los tres setups

- **RETROCESO** (el más temprano): tendencia intacta; en los últimos 3 días el
  precio bajó hasta la zona de la EMA20; hoy cierra verde por encima de ella, con
  el RSI subiendo y entre 40 y 60, sin estar a más de 0,9 ATR de la EMA20.
- **RUPTURA**: 20 días de base estrecha (rango ≤ 6 ATR) que se rompen al cierre
  con volumen ≥ 1,5× el promedio, sin estiramiento (≤ 8% sobre la EMA50).
- **IMPULSO**: la señal técnica de FigAnd (momentum confirmado) más el filtro
  anti-extensión: no más de 1,6 ATR sobre la EMA20 y RSI ≤ 70.

Prioridad si coinciden: RETROCESO > RUPTURA > IMPULSO.

---

## 4. La operación (bracket Alba 2/4)

| Elemento | Regla |
|---|---|
| Entrada | **Orden límite** en cierre − 0,3 ATR |
| Validez | 5 sesiones, desde la sesión **siguiente** al aviso |
| Stop | Entrada − **2 ATR** (se coloca al llenarse y no se mueve) |
| Objetivo | Entrada + **4 ATR** (riesgo/beneficio 1:2) |
| Salida parcial | **No** |
| Tiempo máximo | 45 sesiones; si no tocó nada, se cierra al precio del día |
| Tamaño | Arriesgar una fracción fija del capital (1% por defecto) hasta el stop |

Punto de equilibrio: con 1:2 basta acertar el **33,3%** más los costos.

---

## 5. Lo que dicen los datos (y lo que no)

Antes de fijar el bracket se probó el simulador sobre **498 acciones del S&P 500,
diciembre 2013 – febrero 2018** (datos diarios reales, un periodo distinto al que
se opera). Resultado medio **neto** por operación (costo 0,2%), con una posición
por ticker a la vez:

| Bracket | RETROCESO | RUPTURA | IMPULSO | AZAR en tendencia |
|---|---|---|---|---|
| **ALBA 2/4** (en uso) | +0,39% · obj. 34% | +0,20% · obj. 34% | +0,31% · obj. 34% | +0,42% · obj. 34% |
| FIGAND 1,5/2 | +0,11% | −0,24% | +0,04% | +0,10% |
| Parcial en TP1 + stop a la entrada | −0,05% | −0,38% | −0,10% | −0,03% |
| Amplio 3/6 | +0,73% | +0,41% | +0,60% | +0,70% |

(RETROCESO n = 5.406 operaciones con 2/4; fuera de muestra, desde junio 2016, +0,77%.)

**Tres conclusiones honestas:**

1. **La gestión de la operación importa más que la señal.** Pasar de 1,5/2 a 2/4
   multiplicó el resultado por operación; la salida parcial con stop a la entrada
   fue la peor opción en todos los setups porque recorta las ganadoras. (En la
   auditoría se sugirió esa gestión a partir de 37 operaciones; con 4 años de datos
   no se sostiene, y Alba no la usa.)
2. **En ese periodo ningún setup le ganó a entrar al azar en tendencia** con el
   mismo bracket. La ventaja vino de estar comprado en acciones alcistas, con
   stops amplios y objetivos que dejan correr, no de "adivinar" el día.
   Por eso Alba compara cada setup contra el azar **todos los días** y lo dice en
   cada alerta ("le gana al azar" / "no le gana al azar").
3. **Los setups siguen siendo útiles** porque definen *cuándo* y *dónde* entrar
   con reglas fijas (entrada temprana, sin perseguir), y porque en otros periodos o
   universos pueden sí aportar: eso lo mide el backtest diario sobre **tu**
   universo y **los últimos 5 años** (incluye el mercado bajista de 2022).

Límites: 2013–2018 fue mayormente alcista; el universo S&P 500 de 2018 tiene sesgo
de supervivencia; los resultados diarios del sistema (pestaña 🌅 Alba) son los
que mandan.

---

## 6. Cómo se opera una alerta

1. Llega el aviso (correo/Telegram) después del cierre, con: setup, orden límite,
   stop, objetivo, % de capital para arriesgar 1%, y la frecuencia histórica.
2. Coloca la **orden límite** para la sesión siguiente. Si en 5 sesiones no se
   llena, se descarta. **No se persigue**: si el precio se va, era "LEJOS".
3. Al llenarse, coloca **stop y objetivo** de una vez (orden OCO si tu bróker lo permite).
4. No muevas el stop. No tomes parcial. Si a las 45 sesiones no tocó nada, cierra.
5. Espera rachas: con ~34% de objetivos alcanzados, 5–8 pérdidas seguidas son
   normales. El tamaño fijo es lo que las hace soportables.
6. Revisa el **Historial**: el acierto, la expectativa y el profit factor en vivo
   se calculan con las mismas reglas del backtest.

### Estados del aviso (precio en vivo al enviar)

- 🟢 **EN ZONA**: el precio ya está en o bajo la entrada.
- 🟡 **CERCA**: deja la orden límite; puede llenarse en la sesión.
- 🟠 **LEJOS**: se alejó más de 0,5 ATR; deja la orden y no persigas.
- ⛔ **ANULADA**: ya está bajo el stop; no operar.

---

## 7. Salud del dato (lo que falló en FigAnd)

Cada corrida escribe `data/health.json` y el dashboard muestra el sello
**🩺 Datos OK** o **⛔ Datos incompletos**.

1. Toda descarga pasa por una limpieza que elimina velas vacías o corruptas.
2. La **sesión de referencia** la da SPY (con los festivos NYSE 2026–2027).
3. Si una acción de EEUU no trae esa vela, se **reconstruye** con las velas de
   30 minutos del día (o con Finnhub si configuras `FINNHUB_KEY`). Aparece con 🔧.
4. Si aun así más del **5%** del universo queda sin la vela, el snapshot **no se
   publica** (se conserva el anterior), no se envían alertas y la **corrida de
   respaldo** de las 06:17 ET (07:17 en invierno) lo repite.
5. Las filas con dato viejo se ven atenuadas en el Radar y nunca generan alertas.

Horarios (UTC en GitHub): cierre a las 20:20 y 21:20 (uno sirve en horario de
verano y otro en invierno; la compuerta deja correr solo el correcto), respaldo
a las 11:17 de martes a sábado, y seguimiento intradía del historial a las 15:05 y 18:05.

---

## 8. Qué mirar en cada pestaña

| Pestaña | Uso en Alba |
|---|---|
| 📡 Radar | Filtro general. Etiqueta 🌅 = setup de hoy; "Obj. Alba" = objetivo del bracket; filas grises = dato viejo |
| 🌅 **Alba** | Alertas 4/4, setups del día en el universo principal y en el Listado completo (con los descartes de cada filtro), backtest del protocolo real (vs. azar, dentro/fuera de muestra, comparación de brackets) y resultados en vivo |
| 🎯 COMBO | Perfiles del Excel **en observación** (P3 fusionado con P2, P4 desactivado) |
| 🔎 Screener | Filtros y patrones al cierre, sin cambios |
| 🧠 Analysis | Fundamentales (calidad del negocio) |
| 🎯 Entry Zones | Setups de hoy (o todo lo que está en tendencia) con las zonas Alba y su frecuencia |
| 🎲 Game Theory | Contexto **ilustrativo**; zonas ya unificadas con Alba |
| 📊 BT Entry / 📈 BT Game | Backtest clásico cierre a cierre (se recalcula los viernes); no es el protocolo |
| 🔬 Hessian | Aceleración de precio y volumen (contexto de momentum) |
| 📡 Terminal | Amplitud de mercado |
| 📋 Historial | Resultados reales con las reglas del backtest; las alertas de FigAnd muestran su resultado original tachado |
| 🔗 Markov / 🌊 Laplace | **Ilustrativas** (coeficientes fijos) |

---

## 9. Configuración (variables de entorno opcionales)

| Variable | Por defecto | Qué controla |
|---|---|---|
| `ALBA_MAX_NUEVAS` | 5 | Alertas nuevas por día |
| `ALBA_MAX_SECTOR` | 2 | Posiciones abiertas por sector |
| `ALBA_RIESGO_PCT` | 1 | % del capital arriesgado por operación (para el tamaño sugerido) |
| `ALBA_SETUPS` | RETROCESO,RUPTURA,IMPULSO | Setups que pueden alertar |
| `EARNINGS_BLACKOUT_DAYS` | 5 | Días antes de resultados en que no se alerta |
| `ALBA_MIN_PRECIO` | 5 | Precio mínimo (USD) para alertar |
| `ALBA_MIN_DOLAR_VOL_M` | 5 | Volumen mínimo en millones de USD/día |
| `ALBA_MAX_ENRIQUECER` | 150 | Candidatos del Listado que reciben fundamentales por día |
| `FIGAND_BUDGET_MIN` | 30 | Minutos máximos del escaneo del Listado por corrida |
| `MAX_STALE_PCT` | 5 | % máximo del universo sin la vela para publicar |
| `LEGACY_BACKTEST` | weekly | Backtest clásico: `weekly` (viernes), `always` o `never` |
| `FINNHUB_KEY` | — | Segunda fuente para reconstruir velas |

Se definen en el workflow (`env:`) o como *Variables* del repositorio.
El bracket (0,3 / 2 / 4 ATR, 5 sesiones, 45 de expiración) está en
`scripts/alba_protocol.py` → `BRACKET`; si lo cambias, cambian a la vez las
alertas, el seguimiento y el backtest.

---

## 10. Preguntas frecuentes

**¿Por qué hay días sin alertas?** Porque ninguna acción cumplió las cuatro capas,
el régimen es bajista, los datos no quedaron completos, o se alcanzaron los topes.
Es el comportamiento correcto.

**¿Por qué el acierto (~34–40%) es más bajo que el de FigAnd?** Porque FigAnd medía
mal (fills imposibles, 95% inventado) y usaba un bracket que necesitaba 42,9% para
no perder. Con 1:2, 34% basta para ganar; lo que importa es la **expectativa** por
operación y el **profit factor**, que el Historial muestra.

**¿Qué pasó con las 49 alertas de FigAnd?** Se re-evalúan con las reglas corregidas
en la primera corrida del seguimiento. Algunas "ganadoras" pasan a SIN FILL porque
el precio nunca volvió a la entrada después del aviso.

**¿El COMBO sirve?** Hoy no hay evidencia de ventaja en vivo. Se mantiene para que
sigas observándolo; las alertas no dependen de él.

⚠️ Información educativa. No es asesoría financiera ni recomendación de inversión.
