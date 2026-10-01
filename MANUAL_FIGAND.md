> **Cambios en Alba (septiembre 2026):** el COMBO queda **en observación**. P3 se fusionó con P2 (en el Excel eran las mismas 14 operaciones en 8 fechas); P4 se desactivó (el Excel usa la Dif de velas de 1 hora, calculada como EMA200 − EMA20, y el sistema solo tiene velas diarias; además el código usaba el signo invertido). Los niveles se llaman "coincidencia" en lugar de "alerta", y los perfiles solo se actualizan con operaciones del bracket FigAnd (1,5/2) para no mezclar protocolos. En vivo (11 sesiones) no mostraron ventaja sobre el mercado. Las alertas Alba no dependen del COMBO.

# 🎯 FIGAND SCANNER PRO — Motor Estadístico COMBO

## Qué es

FigAnd Scanner Pro **es** AndFig Scanner Pro con un módulo añadido. Todas las pestañas, fórmulas, columnas, el Historial y la metodología de señales siguen funcionando exactamente igual. Lo nuevo es la pestaña **COMBO**: un motor que convierte el análisis estadístico de tu propio historial en reglas activas de selección diaria.

La arquitectura sigue el circuito que pediste:

```
Señales actuales → Historial → Análisis estadístico → Perfiles combo
      → Motor de reglas FIGAND → Scanner diario → Ranking de oportunidades
```

## Aislamiento del código (regla 20)

| Componente | Archivo | Función |
|---|---|---|
| Sistema original | `index.html`, `scripts/build_data.py` | Intacto |
| **Motor FIGAND** | `figand_engine.js` | Reglas, score y alertas — **archivo separado** |
| Base estadística | `data/figand_profiles.json` | Perfiles regenerables |
| Recálculo | `scripts/figand_stats.py` | Actualiza perfiles con el historial |
| Universo | `data/universe.json` | 11.525 tickers con compañía, sector e industria |
| Variables | `scripts/build_data.py` → `r.fg` | Réplica en Python de las fórmulas del dashboard |

Si `figand_engine.js` fallara, el resto del sistema sigue funcionando sin cambios.

## Las variables — de dónde sale cada una

No se inventó ningún indicador. Cada condición usa la variable que el sistema ya calculaba:

| Variable del estudio | Origen real en el sistema |
|---|---|
| Earliness / ≠Temprano | `earlinessScore()` del dashboard, replicada en Python (`fg_earliness`) |
| Fase (Acumulación) | Estado del radar: ACCUM → Acumulación, ENTRY → Señal activa, ENTRY+ → Señal máxima |
| Markov (Bullish) | `mkCurrentState()`: score 55-74 → BULLISH, ≥75 → STRONG |
| Dif EMA | `sma20_rel − sma200_rel` (equivalente diario de la "Dif" del estudio) |
| Calidad | `compositeGrade()` sobre el composite fundamental |
| Upside | `upside` del módulo Entry Zones |

**Nota honesta sobre "Dif 1 hora":** el estudio lo midió en gráfico de 1 hora; este sistema es EOD (fin de día), así que la condición usa el equivalente diario. La semántica es la misma (separación entre medias), pero la escala no es idéntica — está señalado como "Dif EMA" para no confundir.

## Los perfiles y su rigor estadístico

| ID | Perfil | Casos cerrados | WR observado | Wilson 95% | Prob. estimada | Confianza |
|---|---|---|---|---|---|---|
| P2 | ≠Temprano + Markov Bullish | 14 | 92.9% | 68.5% | 71.8% | BAJA |
| P3 | **PERFIL COMPLETO** ≠Temprano + Acumulación + Bullish | 14 | 92.9% | 68.5% | 71.8% | BAJA |
| P1 | ≠Temprano + Fase Acumulación | 20 | 85.0% | 64.0% | 70.8% | MEDIA |
| P4 | ≠Temprano + Dif EMA > −2 | 31 | 71.0% | 53.4% | 64.3% | MEDIA |

Tasa base del sistema: **47.3%** (86 WIN / 96 LOSS sobre 182 cerradas).

**Tres números, tres significados distintos** (regla 15):
- **WR observado**: lo que pasó en la muestra. Histórico, no promesa.
- **Wilson 95%**: el límite inferior del intervalo de confianza. Con 14 casos, un 92.9% observado es compatible con un 68.5% real. Es la cifra conservadora.
- **Probabilidad estimada**: el WR contraído hacia la tasa base con 12 pseudo-casos. Es la que alimenta el score, precisamente para que una muestra de 14 no pese como una de 140.

## Hallazgos del estudio que conviene conocer

**1. P2 y P3 son la misma muestra.** Los 19 casos de "≠Temprano + Markov Bullish" son exactamente los mismos que los del "perfil completo": todos ellos estaban además en Acumulación. Añadir esa tercera condición **no aporta información nueva** sobre el histórico disponible. Se conservan ambos porque a futuro pueden separarse, pero hoy activar el "perfil completo" es equivalente a activar P2.

**2. El hallazgo más sólido no es el 92.9%, es "≠Temprano".** Con 145 casos (muestra grande), las señales que NO son "Temprano" ganan 54.2% frente al 42.7% de las "Temprano". Esa diferencia, sobre una muestra amplia, es más confiable que cualquier combinación de 14 casos.

**3. Riesgo de minería de datos.** El estudio evaluó más de 50 reglas y se quedó con las mejores. Cuando se prueban 50 hipótesis, algunas destacan por azar. Por eso el sistema usa Wilson y contracción bayesiana en vez del win rate crudo, y por eso los perfiles deben revalidarse con datos nuevos.

**4. Sectores.** Healthcare (75%, 25 casos) y Energy (70.8%, 53 casos) rinden muy por encima; Technology (14.3%, 13 casos) muy por debajo. La muestra de Technology es pequeña, pero merece vigilancia.

## FIGAND SCORE (0-100)

| Componente | Puntos | Qué mide |
|---|---|---|
| Evidencia estadística | 45 | Probabilidad estimada del mejor perfil, multiplicada por un factor de confianza de muestra |
| Confluencia | 15 | Cuántos perfiles combo independientes coinciden (1→7, 2→11, 3+→15) |
| Earliness | 10 | ≠Temprano en zona madura/fresca |
| Markov | 8 | STRONG 8 · BULLISH 6 · NEUTRAL 3 · BEARISH 0 |
| Fase | 7 | Acumulación 7 · Señal máxima 5 · Señal activa 3 |
| Medias móviles | 6 | Dif EMA > −2 |
| Momentum | 5 | 20D en rango saludable |
| Volumen | 4 | Volumen relativo |

**Niveles de alerta:** 🔴 MÁXIMA (score ≥78 + ≥2 combos + Wilson ≥55%) · 🟠 ALTA (≥64 + ≥1 combo) · 🟡 MEDIA (≥48) · ⚪ OBSERVACIÓN.

## La pestaña COMBO

**Ranking del día**: las tres mejores oportunidades en tarjetas destacadas, y debajo la tabla completa ordenada por score → win rate → confluencia → fuerza.

**Sin duplicados** (regla 9): una fila por ticker, con todos sus perfiles listados y su puntuación de confluencia.

**Filtros**: nivel de alerta, solo combo, perfil completo, ≠Temprano, Acumulación, Markov Bullish, score mínimo, win rate mínimo, sector y buscador por ticker o nombre de compañía.

**Ficha individual**: al hacer clic en cualquier fila se despliega la explicación completa — identificación (ticker, compañía, sector, industria), condiciones evaluadas con ✓/✗, perfiles activados con su estadística, el desglose visual del score componente por componente, y todas las variables técnicas.

**Buscador con nombres reales**: escribir "Apple" encuentra AAPL, "NVIDIA" encuentra NVDA, y "F" encuentra Ford Motor Company. Resuelve el problema de los tickers de una sola letra.

## Actualización automática de las estadísticas (regla 14)

`scripts/figand_stats.py` corre en cada workflow y:
- Suma las operaciones cerradas propias (`data/alerts_history.json`) a los casos semilla del estudio.
- Recalcula casos, WIN, LOSS, win rate, Wilson y probabilidad estimada.
- Recalcula el rendimiento medio.
- **Reclasifica la etiqueta combo dinámicamente**: un perfil es combo si tiene ≥12 casos cerrados y su Wilson 95% supera la tasa base en 5 puntos. No es texto fijo: un perfil puede perder la etiqueta si deja de funcionar, y otro puede ganarla.

Para que esto funcione, cada señal registra sus variables FIGAND en el momento de emitirse (`fg` en el historial). Los perfiles evolucionarán a medida que el historial crezca.

## Advertencia final

El sistema muestra **win rate histórico** y **probabilidad estimada** como cifras distintas a propósito. Un 92.9% sobre 14 casos no significa 92.9% de probabilidad futura: significa que en 14 ocasiones pasadas funcionó 13 veces, y que con esa evidencia lo razonable es esperar algo cercano al 70%. FIGAND ordena oportunidades por calidad de evidencia; no predice el futuro ni garantiza resultados.

⚠️ Sistema educativo e informativo. No es asesoría financiera. Toda inversión implica riesgo de pérdida.


## El universo: 11.525 símbolos del Listado

El sistema trabaja con el universo completo de la hoja Listado, en dos niveles:

| Nivel | Tickers | Qué se calcula | Frecuencia |
|---|---|---|---|
| **Núcleo** (`GROUPS` de build_data.py) | ~1.170 | Todo: fundamentales, Buffett, MOS, patrones, backtest, alertas | Cada día |
| **Ampliado** (`scripts/figand_scan.py`) | ~11.500 operables del Listado | Variables de precio + perfiles combo | Cobertura rotatoria |
| **Identificación** (`data/universe.json`) | 11.525 | Compañía, sector, industria — buscador y fichas | Estático |

**Por qué dos niveles.** El pipeline principal consulta los fundamentales de cada ticker uno por uno (necesario para Buffett y margen de seguridad), lo que hace inviable procesar 11.500 símbolos en una ejecución. Pero los cuatro perfiles combo **solo necesitan variables derivadas del precio** (earliness, fase, Markov, Dif EMA), y eso permite descarga por lotes de 120 símbolos — órdenes de magnitud más rápida.

**Cobertura rotatoria.** Cada ejecución procesa tantos lotes como permita su presupuesto de tiempo (25 minutos por defecto) y guarda el índice donde se quedó; la siguiente continúa desde ahí. En unas pocas jornadas se recorre el universo completo, y los resultados se acumulan entre rondas. La cabecera de la pestaña COMBO muestra el porcentaje cubierto.

Las filas provenientes del universo ampliado llevan la marca **◈** y no tienen puntuación Buffett ni margen de seguridad — solo las variables de precio que los perfiles combo requieren. Es una limitación consciente, no un olvido.

Variables de entorno: `FIGAND_BUDGET_MIN` (minutos por ronda), `FIGAND_BATCH` (tamaño de lote), `FIGAND_INCLUDE_ETF` (1/0), `FIGAND_MAX_OUT` (máximo de filas guardadas).

## Un hallazgo contraintuitivo que conviene entender

Al probar el motor apareció algo que el propio estudio ya insinuaba: **"Earliness ≠ Temprano" excluye precisamente los setups que parecen de manual**. Una acción con RSI 52, +5% en 20 días y pegada a su media obtiene earliness 100 → etiqueta TEMPRANO → **queda fuera de los cuatro perfiles combo**.

Los perfiles seleccionan lo contrario: earliness bajo (MADURO, TARDÍO o EXTENDIDO). Y los datos lo respaldan: "Temprano" rindió 42.7% frente a 52.8% de "Maduro/Tardío/Extendido" sobre 206 casos.

Esto merece una lectura cuidadosa. Hay dos explicaciones posibles y solo el tiempo dirá cuál pesa más: puede ser que la fórmula `earlinessScore` esté mal calibrada y su etiqueta "Temprano" señale en realidad indecisión (RSI neutro, sin momentum) más que oportunidad; o puede ser una particularidad del periodo analizado. Conviene vigilarlo conforme crezca el historial, porque implica que el sistema prefiere entrar en movimientos ya iniciados — justo la tensión opuesta a la hipótesis de LeyFig Scanner Pro. Tener ambos sistemas corriendo en paralelo permitirá resolver esa pregunta con datos y no con opiniones.