"""
Streamlit wrapper for Alba Scanner Pro.
Serves the static HTML dashboard when deployed to Streamlit Cloud.
For GitHub Pages, use index.html directly.
"""
import streamlit as st
import subprocess, os, json

st.set_page_config(page_title="Alba Scanner Pro", page_icon="🌅", layout="wide")

# Build data if not present
if not os.path.exists("data/snapshot.json"):
    with st.spinner("Building scanner data (first run, ~10 min)..."):
        subprocess.run(["python", "scripts/build_data.py", "--out-dir", "data", "--skip-backtest"], check=True)

with open("index.html", "r", encoding="utf-8") as f:
    html = f.read()

# Streamlit no sirve archivos estáticos relativos, así que inyectamos los JSON
# inline y parcheamos window.fetch para interceptar las rutas 'data/*.json'.
# (Más robusto que reemplazar strings exactos del HTML, que se rompía al
# cambiar comillas o formato en index.html.)
inline = {}
for name in ("snapshot", "alerts", "alerts_history", "protocol_bt", "health", "figand_profiles", "figand_scan", "universe"):
    path = f"data/{name}.json"
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            inline[name] = json.load(f)

shim = f"""<script>
window._INLINE_DATA = {json.dumps(inline)};
(function() {{
  const orig = window.fetch.bind(window);
  window.fetch = function(url, ...args) {{
    if (typeof url === "string") {{
      for (const key of Object.keys(window._INLINE_DATA)) {{
        if (url.includes(key + ".json")) {{
          return Promise.resolve(new Response(
            JSON.stringify(window._INLINE_DATA[key]),
            {{ status: 200, headers: {{ "Content-Type": "application/json" }} }}
          ));
        }}
      }}
    }}
    return orig(url, ...args);
  }};
}})();
</script>"""

html = html.replace("</head>", shim + "\n</head>") if "</head>" in html else shim + html

st.components.v1.html(html, height=900, scrolling=True)
