# RandomFlix 2.0 — Project Context & Agent Rules

This file is automatically loaded by Antigravity at the start of every chat in `/Users/bmercado/dev/randomflix`.

## 1. Overview & Live Environment
- **Purpose:** A living-room-friendly "channel surfing" web app (mobile PWA + Hisense U8H Google TV browser app via TV Bro / BrowseHere) that eliminates streaming decision fatigue.
- **Live GitHub Pages App:** `https://bmercado-1.github.io/randomflix/` (served from `docs/` on the `main` branch of `bmercado-1/randomflix`).
- **Local Dev Server:** `python3 scripts/dev_server.py 8765` → `http://localhost:8765/` (serves `docs/` and exposes `POST /api/save-local` so clicking **💾 Save & Enrich Locally** in the browser writes `data/shows_source.json` and runs `scripts/enrich_catalog.py` locally without needing GitHub Actions).

## 2. Key Repository Files
- `data/shows_source.json`: Canonical source-of-truth show list (currently seeded with 33 hand-picked Category 1 `Watched` shows; Category 2 and 3 shows will be added incrementally as requested by the user).
- `scripts/enrich_catalog.py`: Zero-dependency Python 3 stdlib enrichment pipeline. Queries JustWatch US GraphQL (`https://apis.justwatch.com/graphql`) for series & per-episode streaming links and TVMaze (`https://api.tvmaze.com`) for posters, runtimes, years, and episode guides. Caches raw API responses in `data/enrichment_cache.json` and outputs `docs/data/catalog.json`.
- `scripts/dev_server.py`: Local HTTP server (`localhost:8765`) with `/api/save-local` endpoint.
- `scripts/manage_shows.py`: Interactive terminal CLI to list, add, recategorize, or remove shows and re-run enrichment.
- `docs/`: Static PWA (`index.html`, `styles.css`, `app.js`, `manifest.json`, `.nojekyll`, `data/catalog.json`).
- `.github/workflows/enrich.yml`: GitHub Actions workflow triggered on pushes to `main` touching `data/shows_source.json` or `scripts/enrich_catalog.py` (plus a weekly Sunday cron with `--refresh` and `workflow_dispatch`). Auto-runs `scripts/enrich_catalog.py` and commits updated `docs/data/catalog.json` and `data/enrichment_cache.json`.
- `legacy/`: Archived 2021–2023 Python CLI/Tkinter/Flask files and old 229-show `shows.csv`. *(User plans to delete `legacy/` once v2.0 is fully settled.)*

## 3. Categories, Watch Modes & Product Rules
- **3 Show Categories:**
  - **Category 1 (`Watched` / Comfort Rewatch):** Already-watched shows (`watched: true`). Always safe for background viewing or rewatching regardless of genre.
  - **Category 2 (`Background` / Episodic):** Unwatched shows that strictly pass the **"Couch Doze-Off Test"** — sitcoms, animated/workplace comedies, pure case-of-the-week procedurals, or sketch/anthology shows where missing 10 minutes doesn't hurt. Never classify plot-heavy serialized dramas into Category 2.
  - **Category 3 (`Active` / Serialized):** Unwatched serialized, mystery-box, or high-attention shows that must be watched sequentially with full focus.
- **4 Watch Modes in UI:**
  - `Mode 2` (`🛋️ Background` = Cat 1 + 2, **Default**)
  - `Mode 1` (`🔁 Comfort Rewatch` = Cat 1 only)
  - `Mode 3` (`🎬 Active Focus` = Cat 3 only)
  - `Mode 4` (`🎰 Full Random` = Cat 1 + 2 + 3)
- **Random Episode Roller (`🎲 Roll Random Episode`):**
  - Must remain **strictly opt-in** (hidden by default when flipping channels). Default viewing is sequential ("resume next unwatched episode").
  - When clicked, displays 1-click direct episode playback buttons (`▶ Play S##E## on <Service>`) and TV app intents (`📺 <Service> TV App (S##E##)`).
- **No LiveChart Auto-Import:** Do not bulk-import from the user's LiveChart anime list; only add specific shows the user chooses.

## 4. Streaming & Deep-Link Rules (Critical — Do Not Regress)
1. **Default Series Links Must Open Series Hubs (Never Autoplay S1E1):**
   - Primary `▶ Open on <Service>` links must open the **Series Hub page** so the streaming app resumes the user's current episode bookmark rather than restarting Episode 1.
   - `sanitize_series_url()` strips episode suffixes from Peacock (`/seasons/1/episodes/...`), Paramount+ (`/video/...`), and Pluto TV (`/season/...`), and resolves Hulu `/watch/<uuid>` URLs to `/series/<slug>-<uuid>` via HTTP redirect (`resolve_hulu_series_url`) or `SERIES_HUB_OVERRIDES`.
2. **Strict JustWatch Provider Matching (`JUSTWATCH_PROVIDER_MAP`):**
   - Never fall back to hostname matching (`watch.amazon.com`) on JustWatch offers — Amazon Channel add-ons like `cra` (Crunchyroll Amazon Channel) use `watch.amazon.com` URLs and cause false-positive `prime_video` links requiring paid add-on subscriptions.
   - Do not include defunct Funimation (`fmn` or `/watch/GE000*` episode links).
3. **Hulu-on-Disney+ Automatic Mapping:**
   - US Hulu series (`/series/<slug>-<36-char-uuid>`) share the exact same 36-char BAMTech/Disney entity UUID on Disney+ (`https://www.disneyplus.com/browse/entity-<36-char-uuid>`), and Hulu episode links (`/watch/<ep-uuid>`) map to `https://www.disneyplus.com/play/<ep-uuid>`.
   - `normalize_providers_list()` automatically synthesizes `disney_plus` series and episode links for every Hulu show even when JustWatch only tags `hlu`.
4. **Netflix Android TV Intents (`com.netflix.ninja`):**
   - On Android TV / Google TV (`com.netflix.ninja`), `intent://` links land on the home screen unless they include `?source=30` and the String extra `S.source=30;`.
   - Both `📺 Launch Netflix TV App` (`/title/<id>?source=30` + `S.source=30`) and `📺 Netflix TV App (Direct Resume)` (`http://www.netflix.com/watch/<series_id>?source=30` + `S.source=30`) are rendered for Netflix shows.
5. **Never Trust Web Search Summaries for Streaming UUIDs/IDs:**
   - Search grounding summaries can hallucinate characters in Crunchyroll series IDs (e.g., `GRGGPG93R`) or Hulu UUIDs. Always verify URLs via HTTP redirect (`resolve_hulu_series_url`), JustWatch GraphQL, or direct page inspection.
6. **Git Sync Note:**
   - Because `.github/workflows/enrich.yml` pushes an auto-enrichment commit to `main` whenever `data/shows_source.json` or `scripts/enrich_catalog.py` changes, always run `git pull --rebase origin main` before pushing new commits.

## 5. UI & Sync Guardrails
- **Always Keep Both Local & Cloud Save Paths:** In the Manage Shows modal (`docs/index.html`, `docs/app.js`), always maintain both `💾 Save & Enrich Locally` (backed by `scripts/dev_server.py` on `localhost`) and `☁️ Save & Sync to GitHub` (for mobile/GitHub Pages). Never remove local-only save workflows.
- **Unsaved Change Recovery:** Always preserve the `↺ Discard Unsaved (N)` button and the `Queued Changes` bar with individual `↺ Undo` pills so accidental removals or category changes can be reverted before syncing.
- **GitHub Token Scope:** In-app GitHub Sync (`PUT /repos/bmercado-1/randomflix/contents/data/shows_source.json`) only requires a Fine-Grained PAT scoped to `bmercado-1/randomflix` with `Contents: Read and write` (or Classic PAT with `public_repo`). `Actions` permissions are not required because `.github/workflows/enrich.yml` triggers automatically on `push`.
