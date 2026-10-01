# 📱 Manual — Alba Scanner Pro en iPhone

## Qué es

La app móvil de Alba Scanner Pro es una **PWA (Progressive Web App)**: se instala en tu iPhone con su propio ícono, se abre a pantalla completa como cualquier app, funciona sin conexión con los últimos datos descargados, y **siempre muestra la información más reciente publicada en tu GitHub** — sin App Store, sin Mac, sin cuenta de desarrollador de $99/año, y sin esperar revisiones de Apple cada vez que cambies algo.

## Instalación en el iPhone (2 minutos)

1. Abre **Safari** (debe ser Safari, no Chrome) y entra a tu sitio: `https://TU_USUARIO.github.io/TU_REPO/movil.html`
2. Toca el botón **Compartir** (el cuadrado con la flecha hacia arriba).
3. Desliza y toca **"Añadir a pantalla de inicio"**.
4. Confirma el nombre "Alba" y toca **Añadir**.

Listo: el ícono del radar aparece en tu pantalla de inicio y la app abre a pantalla completa, sin barra de navegador.

Nota: si entras al dashboard normal (`index.html`) desde un celular, te redirige automáticamente a la versión móvil. Para forzar la vista de escritorio en el celular, usa `index.html?desktop`.

## Cómo se actualiza "en tiempo real"

Este es el flujo completo, y explica por qué **cualquier cambio que hagas en los archivos `.py` se refleja en la app sin tocarla**:

```
Tú editas build_data.py o check_alerts.py en GitHub
        ↓
GitHub Actions ejecuta tus scripts (diario + 3 chequeos intradía,
o al instante si lanzas el workflow manualmente)
        ↓
Tus scripts generan data/snapshot.json, backtest.json, alerts.json
        ↓
GitHub Pages publica los JSON actualizados
        ↓
La app los sondea cada 60 segundos (y al volver a abrirla)
        ↓
Lo que ves en el iPhone es exactamente lo que tu código calculó
```

La app no tiene datos propios ni lógica de negocio duplicada: **renderiza dinámicamente lo que venga en los JSON**. Por eso:

- Si añades un **grupo nuevo** de tickers en `GROUPS` dentro de `build_data.py`, aparece como sección nueva en la pestaña Radar.
- Si añades un **campo nuevo** a cada ticker (por ejemplo `"mi_indicador": valor` en el diccionario `row`), aparece automáticamente en la ficha de detalle del ticker, en la sección "Otros campos del snapshot".
- Si cambias umbrales, fórmulas o el universo, los nuevos resultados se ven en la siguiente ejecución del workflow.

Para ver un cambio **al instante** sin esperar el cron: ve a *Actions → Full Refresh + Backtest → Run workflow* (o el de alertas con modo quick, que tarda ~3 min), y cuando termine, la app lo recoge en su siguiente sondeo de 60 s (o toca ⟳).

## Las 5 pestañas

**◉ Inicio** — el pulso del sistema: régimen de mercado (la franja superior de toda la app se tiñe de verde/ámbar/rojo según BULL/NEUTRAL/BEAR), KPIs del universo (tickers, cuántos en ENTRY, alertas 4/4, empresas MOAT) y los mayores movimientos del día.

**⌖ Radar** — todos los grupos y tickers con buscador. Cada tarjeta muestra estado, AI, calidad Buffett, RS, MOS y las micro-barras de rendimiento 1D/5D/20D. Toca cualquier ticker para abrir su ficha completa con **gráfico en vivo de TradingView** (eso sí es tiempo real tick a tick), todos los indicadores técnicos y fundamentales, y los campos extra que hayas añadido.

**▲ Top** — rankings del universo: mejor score técnico, mejor calidad Buffett, mayor fuerza relativa, mayor margen de seguridad y mayor upside proyectado.

**∿ Backtest** — por cada ticker, la comparación que importa: Baseline (comprar sin filtro) vs señal Técnica vs señal con filtro de Régimen, con el edge en puntos calculado.

**⚑ Alertas** — las alertas 4/4 del último chequeo con su setup, orden límite, stop, objetivo, % de capital sugerido y frecuencia histórica real; los resultados en vivo del Historial; y la lista en observación. **∿ Protocolo** muestra el backtest del protocolo real.

## Detalles honestos

Los **precios y métricas del scanner son del cierre** (el sistema es EOD por diseño anti-repaint); la marca de tiempo visible arriba te dice de cuándo son. El **gráfico de TradingView dentro de cada ficha sí es en vivo**. La app sondea cada 60 segundos, así que "tiempo real" aquí significa: siempre la última versión que tus scripts hayan publicado, automáticamente.

Si la app muestra "DATOS DEMO" o "SIN RÉGIMEN", es que el snapshot publicado aún es el de demostración — lanza el workflow Full Refresh y desaparecerá.

## Solución de problemas

**"No se pudo cargar snapshot.json"**: GitHub Pages aún no publicó, o la ruta cambió. Verifica que `https://TU_USUARIO.github.io/TU_REPO/data/snapshot.json` abra en el navegador.

**La app muestra datos viejos**: toca ⟳. Si persiste, el workflow no ha corrido — revisa la pestaña Actions del repo.

**No aparece "Añadir a pantalla de inicio"**: debes usar Safari; otros navegadores en iOS no lo permiten.
