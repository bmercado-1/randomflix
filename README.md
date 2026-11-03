# 📺 RandomFlix 2.0 — Couch Channel Surfer

A living-room-friendly "channel surfing" web app (PWA & Google TV browser compatible) for picking what to watch without decision fatigue.

## Live App (GitHub Pages)
- **URL:** `https://bmercado-1.github.io/randomflix/`

## Watch Modes
- **🛋️ Mode 2 — Background (`Cat 1 + 2`, Default):** Already-watched comfort shows + low-stakes episodic shows that pass the "Couch Doze-Off Test".
- **🔁 Mode 1 — Comfort Rewatch (`Cat 1 Only`):** Shows you have already watched and can put on anytime.
- **🎬 Mode 3 — Active Focus (`Cat 3 Only`):** Unwatched serialized / plot-heavy shows that require full attention and sequential viewing.
- **🎰 Mode 4 — Full Random (`Cat 1 + 2 + 3`):** Anything in the rotation.

## Local Development & Editing Shows
1. **Start the local server (with 1-click local save & enrichment):**
   ```bash
   python3 scripts/dev_server.py 8765
   ```
   Open `http://localhost:8765` and use **⚙️ Manage Shows → 💾 Save & Enrich Locally**.
2. **Or use the interactive CLI:**
   ```bash
   python3 scripts/manage_shows.py
   ```
3. **Or edit `data/shows_source.json` directly and run:**
   ```bash
   python3 scripts/enrich_catalog.py
   ```
