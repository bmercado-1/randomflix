---
name: randomflix-show-curation
description: >-
  Use this skill when the user asks to add, curate, recategorize, or audit TV shows
  or anime in RandomFlix (including picking Category 2 Background or Category 3 Active
  shows from legacy/shows.csv or new titles), or when debugging broken streaming links.
---

# RandomFlix Show Curation & Link Verification Skill

## 1. Category 2 vs. Category 3 Rubric ("The Couch Doze-Off Test")
When the user asks to classify unwatched shows (or audit candidates from `legacy/shows.csv`):
- **Category 1 (`Watched` / Comfort Rewatch):** Only for shows the user confirms they have already watched (`watched: true`).
- **Category 2 (`Background` / Episodic):** Must strictly pass the **Couch Doze-Off Test**:
  - Sitcoms, animated comedies, workplace comedies (*Bob's Burgers*, *Psych*, *Parks and Recreation*).
  - Pure case-of-the-week procedurals, sketch comedy, or episodic anthology shows where dozing off for 10 minutes or watching a single episode out of order does not ruin an overarching plot.
  - **Reject** plot-heavy dramas, serialized mysteries, or high-stakes thrillers that were previously misclassified as `2` in `legacy/shows.csv` — reclassify those into **Category 3**.
- **Category 3 (`Active` / Serialized):** Unwatched serialized dramas, mystery-box shows, or story-driven anime requiring sequential viewing and full attention.

## 2. Adding & Enriching Shows
1. Add or update entries in `data/shows_source.json` with:
   - `title`, `watched` (`true` for Cat 1, `false` for Cat 2/3), `category` (`1`, `2`, or `3`), `mediaType` (`"tv"` or `"anime"`), `serialization` (`"watched-comfort"`, `"episodic"`, or `"serialized"`), `vibe`, `categoryReason`, and `moodTags`.
   - Include `"year": YYYY` only when needed to disambiguate remakes/reboots on JustWatch and TVMaze (e.g., *Scrubs* `2001`, *Avatar: The Last Airbender* `2005`, *Hunter x Hunter* `2011`).
2. Run enrichment locally:
   ```bash
   python3 scripts/enrich_catalog.py
   ```

## 3. Verifying Streaming Deep Links (Zero-Hallucination Checklist)
Never guess or trust web-search grounding summaries for alphanumeric streaming IDs:
1. **JustWatch Strict Package Matching:** Ensure offers come only from `JUSTWATCH_PROVIDER_MAP` in `scripts/enrich_catalog.py` (never hostname-match `watch.amazon.com`, which leaks paid Amazon Channel add-ons like `cra`).
2. **Hulu & Disney+ Series Hubs:**
   - Verify Hulu `/watch/<uuid>` offers resolve via `resolve_hulu_series_url()` to `https://www.hulu.com/series/<slug>-<36-char-uuid>`.
   - Confirm `normalize_providers_list()` synthesizes the matching Disney+ hub (`https://www.disneyplus.com/browse/entity-<36-char-uuid>`) and episode `/play/<uuid>` links.
3. **Crunchyroll Series Hubs:**
   - If JustWatch only returns episode-level links or defunct `funimation.com` links for an anime on Crunchyroll, verify the live `/series/<9-char-id>/<slug>` URL via HTTP check or browser inspection and pin it in `SERIES_HUB_OVERRIDES`.
4. **Syncing to GitHub Pages:**
   - Always run `git pull --rebase origin main` before `git push origin main` in case `.github/workflows/enrich.yml` pushed an automated catalog update.
