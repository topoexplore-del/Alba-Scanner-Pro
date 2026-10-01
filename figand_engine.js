/* ═══════════════════════════════════════════════════════════════════
   FIGAND ENGINE (COMBO) — módulo independiente · Alba: P3 fusionado, P4 desactivado
   ───────────────────────────────────────────────────────────────────
   Convierte el análisis estadístico del historial en un motor de reglas
   que selecciona oportunidades diarias.

   ARQUITECTURA (aislada del núcleo de FigAnd Scanner Pro):
     data/figand_profiles.json  → perfiles estadísticos (regenerables)
     data/universe.json         → ticker · compañía · sector · industria
     snapshot.json → r.fg       → variables ya calculadas por el pipeline

   No modifica ninguna función existente del sistema. Si este archivo
   fallara, el resto del dashboard sigue funcionando igual.
   ═══════════════════════════════════════════════════════════════════ */
(function (global) {
  "use strict";

  var FG = {
    profiles: null,
    universe: null,
    ready: false,
    _rows: {}
  };

  // ── Carga de datos ────────────────────────────────────────────────
  FG.load = function () {
    var p1 = fetch("data/figand_profiles.json?v=" + Date.now())
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (d) { if (d) FG.profiles = d; })
      .catch(function () {});
    var p2 = fetch("data/universe.json?v=" + Date.now())
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (d) { if (d) FG.universe = d; })
      .catch(function () {});
    var p3 = fetch("data/figand_scan.json?v=" + Date.now())
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (d) { if (d && d.rows) FG.extra = d; })
      .catch(function () {});
    return Promise.all([p1, p2, p3]).then(function () { FG.ready = !!FG.profiles; });
  };

  // ── Identificación de la compañía ─────────────────────────────────
  FG.info = function (tk) {
    var u = FG.universe && FG.universe[String(tk).toUpperCase()];
    return {
      ticker: tk,
      company: u ? u[0] : "",
      sector: u ? u[1] : "",
      industry: u ? u[2] : ""
    };
  };

  // ── Variables (usa las que el pipeline ya calculó en r.fg) ────────
  FG.vars = function (r) {
    if (r.fg) return r.fg;
    // Respaldo: replicar en cliente si el snapshot es anterior
    var e = (typeof earlinessScore === "function") ? earlinessScore(r) : null;
    var lab = (e != null && typeof earlinessLabel === "function") ? earlinessLabel(e).t : null;
    var mk = (typeof mkCurrentState === "function") ? mkCurrentState(r) : null;
    var fase = r.state === "ENTRY+" ? "Señal máxima" : r.state === "ENTRY" ? "Señal activa"
      : r.state === "ACCUM" ? "Acumulación" : "Espera";
    var dif = (r.sma20_rel != null && r.sma200_rel != null)
      ? Math.round((r.sma20_rel - r.sma200_rel) * 100) / 100 : null;
    return {
      earliness: e, earliness_lab: lab, not_temprano: lab ? lab !== "TEMPRANO" : null,
      fase: fase, markov: mk,
      markov_lab: mk != null ? ["BEARISH", "NEUTRAL", "BULLISH", "STRONG"][mk] : null,
      dif_ema: dif,
      calidad: (typeof compositeGrade === "function" && r.fund != null) ? compositeGrade(r.fund).t : null,
      upside: r.upside
    };
  };

  // ── Condiciones: cada una devuelve true / false / null (sin dato) ──
  var COND = {
    "not_temprano":    function (v) { return v.not_temprano == null ? null : !!v.not_temprano; },
    "fase_acumulacion":function (v) { return v.fase ? v.fase === "Acumulación" : null; },
    "markov_bullish":  function (v) { return v.markov == null ? null : v.markov === 2; },
    "dif_ema_gt_-2":   function (v) { return v.dif_ema == null ? null : v.dif_ema > -2; },
    "calidad_excelente": function (v) { return v.calidad ? v.calidad === "EXCELENTE" : null; },
    "upside_12":       function (v) { return v.upside == null ? null : v.upside >= 12; },
    "laplace_buy":     function (v) { return v.lp_signal ? /BUY|COMPRA/i.test(v.lp_signal) : null; },
    "estab_unstable":  function (v) { return v.estabilidad ? v.estabilidad === "UNSTABLE" : null; }
  };
  FG.CONDLABEL = {
    "not_temprano": "Earliness ≠ Temprano",
    "fase_acumulacion": "Fase = Acumulación",
    "markov_bullish": "Markov = Bullish",
    "dif_ema_gt_-2": "Dif EMA > −2",
    "calidad_excelente": "Calidad = EXCELENTE",
    "upside_12": "Upside ≥ 12%",
    "laplace_buy": "Señal Laplace = buy",
    "estab_unstable": "Estabilidad = unstable"
  };

  // ── FIGAND SCORE (0-100) ──────────────────────────────────────────
  // Pondera la evidencia estadística (con castigo por muestra pequeña)
  // junto a las variables técnicas que el sistema ya calcula.
  function score(r, v, hits) {
    var best = null;
    hits.forEach(function (h) { if (!best || h.wr_est > best.wr_est) best = h; });

    // 45 pts — evidencia del mejor perfil, usando la probabilidad ESTIMADA
    // (contraída hacia la tasa base) y no el win rate crudo.
    var sEv = 0;
    if (best) {
      var conf = best.confianza === "ALTA" ? 1.0 : best.confianza === "MEDIA" ? 0.92 : 0.82;
      sEv = Math.max(0, Math.min(1, (best.wr_est - 0.30) / 0.50)) * 45 * conf;
    }
    // 15 pts — confluencia de perfiles combo independientes
    var nCombo = hits.filter(function (h) { return h.combo; }).length;
    var sConf = nCombo >= 3 ? 15 : nCombo === 2 ? 11 : nCombo === 1 ? 7 : 0;
    // 10 pts — earliness (≠Temprano es lo que el estudio premia)
    var sEar = 0;
    if (v.earliness != null) {
      sEar = v.not_temprano ? (v.earliness >= 40 && v.earliness < 70 ? 10 : 7) : 2;
    }
    // 8 pts — estado Markov
    var sMk = v.markov == null ? 0 : [0, 3, 6, 8][v.markov];
    // 7 pts — fase de Game Theory
    var sFa = { "Acumulación": 7, "Señal máxima": 5, "Señal activa": 3, "Espera": 1 }[v.fase] || 0;
    // 6 pts — proximidad de las medias móviles
    var sDif = 0;
    if (v.dif_ema != null) sDif = v.dif_ema > -2 ? 6 : v.dif_ema > -5 ? 3 : 1;
    // 5 pts — momentum · 4 pts — volumen relativo
    var d20 = r["20d"] || 0;
    var sMom = d20 >= 2 && d20 <= 12 ? 5 : d20 > 12 ? 2 : d20 > 0 ? 3 : 1;
    var rv = r.rel_vol || 0;
    var sVol = rv >= 1.5 ? 4 : rv >= 1.0 ? 3 : rv > 0 ? 1 : 0;

    return {
      total: Math.round(sEv + sConf + sEar + sMk + sFa + sDif + sMom + sVol),
      partes: { evidencia: Math.round(sEv), confluencia: sConf, earliness: sEar,
                markov: sMk, fase: sFa, medias: sDif, momentum: sMom, volumen: sVol },
      best: best, nCombo: nCombo
    };
  }

  // ── Nivel de alerta ───────────────────────────────────────────────
  function level(sc) {
    var b = sc.best;
    var lo = b ? b.wr_lo : 0;
    if (sc.total >= 78 && sc.nCombo >= 2 && lo >= 0.55)
      return { k: "MAX", icon: "🔴", txt: "COINCIDENCIA MÁXIMA", c: "var(--red)" };
    if (sc.total >= 64 && sc.nCombo >= 1)
      return { k: "ALTA", icon: "🟠", txt: "COINCIDENCIA ALTA", c: "var(--orange,#ff9800)" };
    if (sc.total >= 48)
      return { k: "MEDIA", icon: "🟡", txt: "COINCIDENCIA MEDIA", c: "var(--amber)" };
    return { k: "OBS", icon: "⚪", txt: "OBSERVACIÓN", c: "var(--txt3)" };
  }

  // ── Evaluación de un ticker ───────────────────────────────────────
  FG.evaluate = function (r) {
    if (!FG.profiles) return null;
    var v = FG.vars(r);
    var hits = [], condState = {};
    FG.profiles.perfiles.forEach(function (p) {
      if (p.activo === false) return;          // P3 fusionado con P2 · P4 desactivado (Alba)
      var ok = true, known = 0;
      p.cond.forEach(function (c) {
        var f = COND[c], res = f ? f(v) : null;
        condState[c] = res;
        if (res === true) known++;
        else ok = false;
      });
      if (ok) hits.push(p);
    });
    var sc = score(r, v, hits);
    var lv = level(sc);
    var info = FG.info(r.ticker);
    // Perfil completo = cumple P1 y P2 a la vez (el antiguo P3)
    var completo = hits.some(function (h) { return h.id === "P1"; }) &&
                   hits.some(function (h) { return h.id === "P2"; });
    return {
      r: r, v: v, info: info, hits: hits, cond: condState,
      score: sc.total, partes: sc.partes, best: sc.best, nCombo: sc.nCombo,
      level: lv, completo: completo
    };
  };

  // ── Escaneo del universo cargado en el snapshot ───────────────────
  // Combina el universo del snapshot (con fundamentales) y el escaneo
  // extendido del Listado completo (solo precio). Prioriza el snapshot.
  FG.allRows = function (snapRows) {
    var seen = {}, out = [];
    (snapRows || []).forEach(function (r) { if (!seen[r.ticker]) { seen[r.ticker] = 1; out.push(r); } });
    if (FG.extra && FG.extra.rows) {
      FG.extra.rows.forEach(function (r) {
        if (!seen[r.ticker]) { seen[r.ticker] = 1; r._ext = true; out.push(r); }
      });
    }
    return out;
  };

  FG.scan = function (rows) {
    var seen = {}, out = [];
    rows.forEach(function (r) {
      if (seen[r.ticker]) return;      // una sola fila por ticker (regla 9)
      seen[r.ticker] = 1;
      var ev = FG.evaluate(r);
      if (ev) { out.push(ev); FG._rows[r.ticker] = ev; }
    });
    out.sort(function (a, b) {
      if (b.score !== a.score) return b.score - a.score;                  // 1. score
      var wa = a.best ? a.best.wr_est : 0, wb = b.best ? b.best.wr_est : 0;
      if (wb !== wa) return wb - wa;                                      // 2. win rate
      if (b.nCombo !== a.nCombo) return b.nCombo - a.nCombo;              // 3. condiciones
      return (b.r.score || 0) - (a.r.score || 0);                         // 4. fuerza
    });
    return out;
  };

  // ── Buscador: ticker, nombre de compañía o sector ─────────────────
  FG.search = function (q, limit) {
    q = String(q || "").trim().toLowerCase();
    if (!q || !FG.universe) return [];
    var exact = [], starts = [], contains = [];
    for (var tk in FG.universe) {
      var u = FG.universe[tk], tl = tk.toLowerCase(), nl = (u[0] || "").toLowerCase();
      if (tl === q) exact.push(tk);
      else if (tl.indexOf(q) === 0 || nl.indexOf(q) === 0) starts.push(tk);
      else if (nl.indexOf(q) >= 0 || (u[1] || "").toLowerCase().indexOf(q) >= 0) contains.push(tk);
      if (exact.length + starts.length > 400) break;
    }
    return exact.concat(starts.sort(), contains.sort()).slice(0, limit || 25).map(FG.info);
  };

  global.FIGAND = FG;
})(window);
