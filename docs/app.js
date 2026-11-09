/**
 * RandomFlix 2.0 — Couch Channel Surfer App
 * Works on both Mobile (PWA) and Google TV Browsers (TV Bro / BrowseHere with Bluetooth mouse).
 */

const STORAGE_KEYS = {
  CATEGORY_OVERRIDES: "randomflix_cat_overrides_v2",
  DISABLED_OVERRIDES: "randomflix_disabled_overrides_v2",
  REMOVED_IDS: "randomflix_removed_ids_v2",
  CUSTOM_SHOWS: "randomflix_custom_shows_v2",
  SNOOZED_IDS: "randomflix_snoozed_ids_v2",
  LAST_MODE: "randomflix_last_mode_v2",
  LAST_TYPE_FILTER: "randomflix_last_type_v2",
  GH_TOKEN: "randomflix_gh_token_v2",
  GH_REPO: "randomflix_gh_repo_v2",
};

const CATEGORY_LABELS = {
  1: "Cat 1 • Comfort Rewatch (Watched)",
  2: "Cat 2 • Low-Stakes Background",
  3: "Cat 3 • Active / Serialized",
};

const ANDROID_TV_PACKAGES = {
  netflix: "com.netflix.ninja",
  hulu: "com.hulu.livingroomplus",
  max: "com.wbd.stream",
  disney_plus: "com.disney.disneyplus",
  prime_video: "com.amazon.amazonvideo.livingroom",
  crunchyroll: "com.crunchyroll.crunchyroid",
  peacock: "com.peacocktv.peacockandroid",
  paramount_plus: "com.cbs.ott",
  apple_tv_plus: "com.apple.atve.androidtv.appletv",
  pluto_tv: "tv.pluto.android",
  tubi: "com.tubitv",
  hidive: "com.hidive.android",
};

function buildAndroidTvIntent(webUrl, providerId) {
  const pkg = ANDROID_TV_PACKAGES[providerId];
  if (!webUrl || !pkg) return "";
  try {
    const u = new URL(webUrl);
    const scheme = u.protocol.replace(":", "") || "https";
    let hostAndPath = webUrl.replace(/^https?:\/\//i, "");
    const fallbackEncoded = encodeURIComponent(webUrl);
    if (providerId === "netflix") {
      const sep = hostAndPath.includes("?") ? "&" : "?";
      if (!hostAndPath.includes("source=")) {
        hostAndPath = `${hostAndPath}${sep}source=30`;
      }
      return `intent://${hostAndPath}#Intent;scheme=${scheme};package=${pkg};action=android.intent.action.VIEW;S.source=30;S.browser_fallback_url=${fallbackEncoded};end`;
    }
    return `intent://${hostAndPath}#Intent;scheme=${scheme};package=${pkg};action=android.intent.action.VIEW;S.browser_fallback_url=${fallbackEncoded};end`;
  } catch (_) {
    return "";
  }
}

const state = {
  baseCatalog: [],
  customShows: JSON.parse(localStorage.getItem(STORAGE_KEYS.CUSTOM_SHOWS) || "[]"),
  categoryOverrides: JSON.parse(localStorage.getItem(STORAGE_KEYS.CATEGORY_OVERRIDES) || "{}"),
  disabledOverrides: JSON.parse(localStorage.getItem(STORAGE_KEYS.DISABLED_OVERRIDES) || "{}"),
  removedIds: new Set(JSON.parse(localStorage.getItem(STORAGE_KEYS.REMOVED_IDS) || "[]")),
  snoozedIds: new Set(JSON.parse(localStorage.getItem(STORAGE_KEYS.SNOOZED_IDS) || "[]")),
  mode: Number(localStorage.getItem(STORAGE_KEYS.LAST_MODE) || 2), // Default Mode 2: Background (Cat 1 + 2)
  serviceFilter: "all",
  typeFilter: localStorage.getItem(STORAGE_KEYS.LAST_TYPE_FILTER) || "all",
  runtimeFilter: "all",
  deck: [],
  deckIndex: 0,
};

function normalizeId(title) {
  return String(title || "").toLowerCase().replace(/[^a-z0-9]+/g, "");
}

function getAllActiveShows() {
  const combined = [...state.baseCatalog, ...state.customShows];
  const seen = new Set();
  const result = [];
  for (const s of combined) {
    if (!s || !s.id || seen.has(s.id) || state.removedIds.has(s.id)) continue;
    seen.add(s.id);
    result.push(s);
  }
  return result;
}

function getEffectiveCategory(show) {
  if (state.categoryOverrides[show.id]) {
    return Number(state.categoryOverrides[show.id]);
  }
  return show.category;
}

function isShowDisabled(show) {
  if (Object.prototype.hasOwnProperty.call(state.disabledOverrides, show.id)) {
    return Boolean(state.disabledOverrides[show.id]);
  }
  return Boolean(show.disabled);
}

function setShowDisabled(show, disabledVal) {
  const baseDisabled = Boolean(show.disabled);
  if (Boolean(disabledVal) === baseDisabled) {
    delete state.disabledOverrides[show.id];
  } else {
    state.disabledOverrides[show.id] = Boolean(disabledVal);
  }
  saveCustomState();
  renderManagerList();
  rebuildDeck();
}

function countUnsavedChanges() {
  const baseById = new Map(state.baseCatalog.map((s) => [s.id, s]));
  let count = 0;

  for (const cs of state.customShows) {
    if (!baseById.has(cs.id) && !state.removedIds.has(cs.id)) {
      count += 1;
    }
  }
  for (const [id, cat] of Object.entries(state.categoryOverrides)) {
    if (state.removedIds.has(id)) continue;
    const baseShow = baseById.get(id);
    if (baseShow && Number(baseShow.category) !== Number(cat)) {
      count += 1;
    }
  }
  for (const [id, disabledVal] of Object.entries(state.disabledOverrides)) {
    if (state.removedIds.has(id)) continue;
    const baseShow = baseById.get(id);
    if (baseShow && Boolean(baseShow.disabled) !== Boolean(disabledVal)) {
      count += 1;
    }
  }
  for (const id of state.removedIds) {
    if (baseById.has(id)) {
      count += 1;
    }
  }
  return count;
}

function updateUnsavedBadges() {
  const unsaved = countUnsavedChanges();
  const btnOpenManager = document.getElementById("btn-open-manager");
  const btnSaveLocal = document.getElementById("btn-save-local");
  const btnSync = document.getElementById("btn-sync-github");
  const btnDiscard = document.getElementById("btn-discard-changes");

  if (btnOpenManager) {
    btnOpenManager.textContent =
      unsaved > 0 ? `⚙️ Manage Shows (${unsaved} unsaved)` : "⚙️ Manage Shows";
  }
  if (btnSaveLocal) {
    btnSaveLocal.textContent =
      unsaved > 0
        ? `💾 Save & Enrich Locally (${unsaved})`
        : "💾 Save & Enrich Locally";
  }
  if (btnSync) {
    btnSync.textContent =
      unsaved > 0
        ? `☁️ Save & Sync to GitHub (${unsaved})`
        : "☁️ Save & Sync to GitHub";
  }
  if (btnDiscard) {
    btnDiscard.textContent =
      unsaved > 0 ? `↺ Discard Unsaved (${unsaved})` : "↺ Discard Unsaved";
    btnDiscard.classList.toggle("hidden", unsaved === 0);
  }
  renderPendingChanges();
}

function renderPendingChanges() {
  const box = document.getElementById("pending-changes-box");
  if (!box) return;
  box.innerHTML = "";

  const baseById = new Map(state.baseCatalog.map((s) => [s.id, s]));
  const items = [];

  for (const cs of state.customShows) {
    if (!baseById.has(cs.id) && !state.removedIds.has(cs.id)) {
      items.push({
        label: `➕ Added: ${cs.title}`,
        undo: () => {
          state.customShows = state.customShows.filter((s) => s.id !== cs.id);
          saveCustomState();
          renderManagerList();
          rebuildDeck();
        },
      });
    }
  }

  for (const [id, cat] of Object.entries(state.categoryOverrides)) {
    if (state.removedIds.has(id)) continue;
    const baseShow = baseById.get(id);
    if (baseShow && Number(baseShow.category) !== Number(cat)) {
      items.push({
        label: `🏷️ ${baseShow.title}: Cat ${baseShow.category} → Cat ${cat}`,
        undo: () => {
          delete state.categoryOverrides[id];
          saveCustomState();
          renderManagerList();
          rebuildDeck();
        },
      });
    }
  }

  for (const [id, disabledVal] of Object.entries(state.disabledOverrides)) {
    if (state.removedIds.has(id)) continue;
    const baseShow = baseById.get(id);
    if (baseShow && Boolean(baseShow.disabled) !== Boolean(disabledVal)) {
      items.push({
        label: disabledVal ? `🚫 Disabled: ${baseShow.title}` : `✅ Enabled: ${baseShow.title}`,
        undo: () => {
          delete state.disabledOverrides[id];
          saveCustomState();
          renderManagerList();
          rebuildDeck();
        },
      });
    }
  }

  for (const id of state.removedIds) {
    const baseShow = baseById.get(id);
    if (baseShow) {
      items.push({
        label: `🗑 Removed: ${baseShow.title}`,
        undo: () => {
          state.removedIds.delete(id);
          saveCustomState();
          renderManagerList();
          rebuildDeck();
        },
      });
    }
  }

  if (items.length === 0) {
    box.classList.add("hidden");
    return;
  }

  box.classList.remove("hidden");
  const titleSpan = document.createElement("strong");
  titleSpan.textContent = `Queued Changes (${items.length}):`;
  box.appendChild(titleSpan);

  for (const item of items) {
    const pill = document.createElement("span");
    pill.className = "pending-pill";
    const text = document.createElement("span");
    text.textContent = item.label;
    const undoBtn = document.createElement("button");
    undoBtn.type = "button";
    undoBtn.className = "pending-undo-btn";
    undoBtn.textContent = "↺ Undo";
    undoBtn.addEventListener("click", item.undo);
    pill.appendChild(text);
    pill.appendChild(undoBtn);
    box.appendChild(pill);
  }
}

function discardAllUnsavedChanges() {
  state.customShows = [];
  state.categoryOverrides = {};
  state.disabledOverrides = {};
  state.removedIds.clear();
  saveCustomState();
  renderManagerList();
  rebuildDeck();
  showSyncStatus("✓ Discarded all unsaved changes and restored the saved rotation.", false);
}

function saveCustomState() {
  localStorage.setItem(STORAGE_KEYS.CUSTOM_SHOWS, JSON.stringify(state.customShows));
  localStorage.setItem(STORAGE_KEYS.CATEGORY_OVERRIDES, JSON.stringify(state.categoryOverrides));
  localStorage.setItem(STORAGE_KEYS.DISABLED_OVERRIDES, JSON.stringify(state.disabledOverrides));
  localStorage.setItem(STORAGE_KEYS.REMOVED_IDS, JSON.stringify([...state.removedIds]));
  updateUnsavedBadges();
}

function reconcileLocalStateWithCatalog() {
  const baseById = new Map(state.baseCatalog.map((s) => [s.id, s]));

  // Once a custom show has been enriched and published into catalog.json, use the enriched baseCatalog entry
  state.customShows = state.customShows.filter((cs) => !baseById.has(cs.id));

  // Clear category overrides that now match baseCatalog
  for (const [id, cat] of Object.entries(state.categoryOverrides)) {
    const baseShow = baseById.get(id);
    if (baseShow && Number(baseShow.category) === Number(cat)) {
      delete state.categoryOverrides[id];
    }
  }

  // Clear disabled overrides that now match baseCatalog
  for (const [id, disabledVal] of Object.entries(state.disabledOverrides)) {
    const baseShow = baseById.get(id);
    if (baseShow && Boolean(baseShow.disabled) === Boolean(disabledVal)) {
      delete state.disabledOverrides[id];
    }
  }

  // Clear removedIds that are no longer in baseCatalog
  for (const id of [...state.removedIds]) {
    if (!baseById.has(id)) {
      state.removedIds.delete(id);
    }
  }

  saveCustomState();
}

function buildShowsSourcePayload() {
  return {
    shows: getAllActiveShows().map((s) => {
      const cat = getEffectiveCategory(s);
      const disabled = isShowDisabled(s);
      const entry = {
        title: s.title,
      };
      if (s.pinnedYear) {
        entry.year = s.pinnedYear;
      }
      if (disabled) {
        entry.disabled = true;
      }
      entry.watched = cat === 1;
      entry.category = cat;
      entry.mediaType = s.mediaType || "tv";
      entry.serialization =
        cat === 1
          ? "watched-comfort"
          : cat === 3
          ? "serialized"
          : s.serialization || "episodic";
      if (s.vibe && !s.vibe.startsWith("Added from the Manage Shows")) {
        entry.vibe = s.vibe;
      }
      if (
        s.categoryReason &&
        !s.categoryReason.startsWith("Assigned to Category") &&
        s.category === cat
      ) {
        entry.categoryReason = s.categoryReason;
      }
      entry.moodTags = s.moodTags || [];
      return entry;
    }),
  };
}

function matchesWatchMode(show, mode) {
  const cat = getEffectiveCategory(show);
  if (mode === 1) return cat === 1; // Watched only
  if (mode === 2) return cat === 1 || cat === 2; // Background = Watched + Episodic Background
  if (mode === 3) return cat === 3; // Active Serialized only
  return true; // Mode 4 = Full Random
}

function matchesFilters(show) {
  if (isShowDisabled(show)) return false;
  if (state.snoozedIds.has(show.id)) return false;
  if (!matchesWatchMode(show, state.mode)) return false;

  if (state.serviceFilter !== "all") {
    const hasProvider = (show.streamingProviders || []).some(
      (p) => p.id === state.serviceFilter
    );
    if (!hasProvider) return false;
  }

  if (state.typeFilter !== "all") {
    if ((show.mediaType || "tv") !== state.typeFilter) return false;
  }

  const runtime = show.runtimeMinutes || 30;
  if (state.runtimeFilter === "short" && runtime > 32) return false;
  if (state.runtimeFilter === "long" && runtime <= 32) return false;

  return true;
}

function shuffleArray(items) {
  const arr = [...items];
  for (let i = arr.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [arr[i], arr[j]] = [arr[j], arr[i]];
  }
  return arr;
}

function rebuildDeck() {
  const matching = getAllActiveShows().filter(matchesFilters);
  state.deck = shuffleArray(matching);
  state.deckIndex = 0;
  renderCurrentShow();
}

function openShowById(showId) {
  const show = getAllActiveShows().find((s) => s.id === showId);
  if (!show) return false;

  const existingIdx = state.deck.findIndex((s) => s.id === show.id);
  if (existingIdx !== -1) {
    state.deckIndex = existingIdx;
  } else {
    state.deck.splice(state.deckIndex, 0, show);
  }

  document.getElementById("manager-modal")?.classList.add("hidden");
  if (window.history && window.history.replaceState) {
    window.history.replaceState(null, "", `#show=${encodeURIComponent(show.id)}`);
  }
  renderCurrentShow();
  return true;
}

function applyHashShowIfPresent(rawHash = window.location.hash) {
  const hash = (rawHash || "").replace(/^#/, "");
  if (hash.startsWith("show=")) {
    const id = decodeURIComponent(hash.slice("show=".length)).trim();
    if (id) {
      openShowById(id);
    }
  }
}

function pickRandomEpisode(show) {
  const seasons = show.seasons || [];
  const allEpisodes = [];
  for (const s of seasons) {
    for (const ep of s.episodes || []) {
      allEpisodes.push({
        season: s.season,
        ep: ep.ep,
        title: ep.title,
        links: ep.links || {},
      });
    }
  }
  if (allEpisodes.length === 0) {
    return null;
  }
  // Prefer episodes that have direct 1-click streaming links when available
  const linkedEpisodes = allEpisodes.filter((e) => {
    if (!e.links || Object.keys(e.links).length === 0) return false;
    if (state.serviceFilter !== "all") {
      return Boolean(e.links[state.serviceFilter]);
    }
    return true;
  });
  const pool = linkedEpisodes.length > 0 ? linkedEpisodes : allEpisodes;
  return pool[Math.floor(Math.random() * pool.length)];
}

function renderCurrentShow() {
  const statusEl = document.getElementById("pool-status");
  const totalInDeck = state.deck.length;
  const totalDisabled = getAllActiveShows().filter(isShowDisabled).length;
  const disabledNote = totalDisabled > 0 ? ` • ${totalDisabled} disabled` : "";
  statusEl.textContent = `${totalInDeck} show${totalInDeck === 1 ? "" : "s"} in current channel rotation${disabledNote}`;

  // Always hide opt-in random episode box when flipping to a new show
  const epBox = document.getElementById("random-ep-box");
  const btnHideEp = document.getElementById("btn-hide-episode");
  const btnRollEp = document.getElementById("btn-roll-episode");
  epBox.classList.add("hidden");
  btnHideEp.classList.add("hidden");
  btnRollEp.textContent = "🎲 Roll Random Episode (Optional)";

  if (totalInDeck === 0) {
    document.getElementById("show-title").textContent = "No shows match these filters";
    document.getElementById("show-vibe").textContent =
      "Try switching Watch Mode, selecting 'All Apps', or resetting snoozed shows.";
    document.getElementById("show-reason").textContent = "";
    document.getElementById("providers-list").innerHTML = "";
    document.getElementById("show-tags").innerHTML = "";
    document.getElementById("badge-deck-pos").textContent = "0 / 0";
    return;
  }

  const show = state.deck[state.deckIndex];
  const cat = getEffectiveCategory(show);

  // Poster
  const posterImg = document.getElementById("show-poster");
  const posterFallback = document.getElementById("poster-fallback");
  if (show.posterUrl) {
    posterImg.src = show.posterUrl;
    posterImg.style.display = "block";
    posterFallback.style.display = "none";
  } else {
    posterImg.style.display = "none";
    posterFallback.style.display = "flex";
  }

  // Badges
  const catBadge = document.getElementById("badge-category");
  catBadge.textContent = CATEGORY_LABELS[cat] || `Category ${cat}`;
  catBadge.className = `badge badge-cat cat-${cat}`;

  document.getElementById("badge-type").textContent =
    show.mediaType === "anime" ? "Anime" : "TV Series";
  document.getElementById("badge-runtime").textContent = `${show.runtimeMinutes || 30} min`;
  document.getElementById("badge-year").textContent = show.year || "—";
  document.getElementById("badge-deck-pos").textContent = `${state.deckIndex + 1} / ${totalInDeck}`;

  // Title, Vibe & Category Reason
  document.getElementById("show-title").textContent = show.title;
  document.getElementById("show-vibe").textContent = show.vibe || "";
  document.getElementById("show-reason").textContent = show.categoryReason || "";

  // Genres & Mood Tags
  const tagsContainer = document.getElementById("show-tags");
  tagsContainer.innerHTML = "";
  const combinedTags = [...new Set([...(show.genres || []), ...(show.moodTags || [])])];
  for (const tag of combinedTags) {
    const span = document.createElement("span");
    span.className = "tag-pill";
    span.textContent = tag;
    tagsContainer.appendChild(span);
  }

  // Streaming Providers (Series-level links + Android TV Intent links for TV Bro / BrowseHere)
  const providersList = document.getElementById("providers-list");
  providersList.innerHTML = "";
  const providers = show.streamingProviders || [];

  if (providers.length === 0) {
    const emptyMsg = document.createElement("span");
    emptyMsg.className = "ep-label";
    emptyMsg.textContent = "Streaming link not cached yet — use Google TV Search Card:";
    providersList.appendChild(emptyMsg);
  }

  for (const prov of providers) {
    const card = document.createElement("div");
    card.className = "provider-card";

    // Primary button: Direct Web / Universal Link
    const primaryLink = document.createElement("a");
    primaryLink.className = "provider-btn";
    primaryLink.style.backgroundColor = prov.color || "#6366f1";
    primaryLink.href = prov.webUrl;
    primaryLink.target = "_blank";
    primaryLink.rel = "noopener noreferrer";
    primaryLink.textContent = `▶ Open on ${prov.name}`;
    card.appendChild(primaryLink);

    // Explicit Android TV Native App Intent Button (for TV Bro / BrowseHere on Hisense U8H)
    if (prov.androidTvIntentUrl && prov.androidTvIntentUrl.startsWith("intent://")) {
      const tvIntentLink = document.createElement("a");
      tvIntentLink.className = "provider-btn secondary-link";
      tvIntentLink.href = prov.androidTvIntentUrl;
      tvIntentLink.textContent = `📺 Launch ${prov.name} TV App`;
      tvIntentLink.title = "Forces TV Bro / BrowseHere on Google TV to open the native streaming app";
      card.appendChild(tvIntentLink);
    }

    // For Netflix on Android TV (com.netflix.ninja), some builds only route /watch/<id>
    // URIs with S.source=30 (which resumes your current episode when passed a series ID).
    if (prov.id === "netflix" && prov.webUrl) {
      const m = prov.webUrl.match(/\/title\/(\d+)/);
      if (m) {
        const watchUrl = `http://www.netflix.com/watch/${m[1]}`;
        const watchIntent = buildAndroidTvIntent(watchUrl, "netflix");
        if (watchIntent) {
          const tvWatchLink = document.createElement("a");
          tvWatchLink.className = "provider-btn secondary-link";
          tvWatchLink.href = watchIntent;
          tvWatchLink.textContent = "📺 Netflix TV App (Direct Resume)";
          tvWatchLink.title = "Uses /watch/<series_id> + S.source=30 for Android TV builds that ignore /title/ intents";
          card.appendChild(tvWatchLink);
        }
      }
    }

    providersList.appendChild(card);
  }

  // Always offer the Google TV Search Card fallback button
  if (show.googleTvSearchUrl) {
    const gtvLink = document.createElement("a");
    gtvLink.className = "provider-btn secondary-link";
    gtvLink.href = show.googleTvSearchUrl;
    gtvLink.target = "_blank";
    gtvLink.rel = "noopener noreferrer";
    gtvLink.textContent = "🔍 Google TV Card";
    providersList.appendChild(gtvLink);
  }

  // Update Promote button state
  const promoteBtn = document.getElementById("btn-promote-watched");
  if (cat === 1) {
    promoteBtn.textContent = "✓ In Comfort Rewatch (Cat 1)";
    promoteBtn.disabled = true;
  } else {
    promoteBtn.textContent = "✅ Move to Watched (Cat 1)";
    promoteBtn.disabled = false;
  }

  // Update Disable / Enable button state
  const disableBtn = document.getElementById("btn-disable-current");
  if (disableBtn) {
    const disabled = isShowDisabled(show);
    disableBtn.textContent = disabled ? "✅ Enable Show" : "🚫 Disable Show";
    disableBtn.title = disabled
      ? "Re-enable this show in the active channel rotation"
      : "Keep on list, but exclude from the active channel rotation";
  }
}

function renderManagerList() {
  const listEl = document.getElementById("manager-list");
  const query = (document.getElementById("manager-search").value || "").toLowerCase().trim();
  const statusSelect = document.getElementById("manager-status-filter");
  const statusFilter = statusSelect ? statusSelect.value : "all";
  listEl.innerHTML = "";

  const allShows = getAllActiveShows();
  const disabledCount = allShows.filter(isShowDisabled).length;
  const activeCount = allShows.length - disabledCount;

  if (statusSelect && statusSelect.options.length >= 3) {
    statusSelect.options[0].textContent = `All Shows (${allShows.length})`;
    statusSelect.options[1].textContent = `Active in DB (${activeCount})`;
    statusSelect.options[2].textContent = `Disabled Only (${disabledCount})`;
  }

  const shows = allShows.filter((s) => {
    const disabled = isShowDisabled(s);
    if (statusFilter === "active" && disabled) return false;
    if (statusFilter === "disabled" && !disabled) return false;
    if (!query) return true;
    const provNames = (s.streamingProviders || []).map((p) => p.name).join(" ").toLowerCase();
    const mType = (s.mediaType || "tv").toLowerCase();
    const statusText = disabled ? "disabled" : "active enabled";
    return (
      s.title.toLowerCase().includes(query) ||
      mType.includes(query) ||
      provNames.includes(query) ||
      statusText.includes(query)
    );
  });

  for (const show of shows) {
    const cat = getEffectiveCategory(show);
    const disabled = isShowDisabled(show);
    const row = document.createElement("div");
    row.className = disabled ? "manager-row is-disabled" : "manager-row";

    const left = document.createElement("div");
    const provNames = (show.streamingProviders || []).map((p) => p.name).join(", ") || "No provider cached";
    const titleRow = document.createElement("div");
    titleRow.className = "manager-row-title";
    const titleLink = document.createElement("a");
    titleLink.href = `#show=${encodeURIComponent(show.id)}`;
    titleLink.className = "manager-title-link";
    titleLink.textContent = show.title;
    titleLink.title = `Open ${show.title} page in RandomFlix`;
    titleLink.addEventListener("click", (e) => {
      e.preventDefault();
      openShowById(show.id);
    });
    titleRow.appendChild(titleLink);
    if (disabled) {
      const disBadge = document.createElement("span");
      disBadge.className = "disabled-badge";
      disBadge.textContent = "Disabled";
      titleRow.appendChild(disBadge);
    }
    const subRow = document.createElement("div");
    subRow.className = "subtitle";
    subRow.textContent = `${show.mediaType === "anime" ? "Anime" : "TV"} • ${provNames}`;
    left.appendChild(titleRow);
    left.appendChild(subRow);

    const actions = document.createElement("div");
    actions.className = "manager-row-actions";

    const disableLabel = document.createElement("label");
    disableLabel.className = disabled ? "disable-toggle checked" : "disable-toggle";
    disableLabel.title = "Keep on list, but exclude from the active database rotation";
    const disableCheckbox = document.createElement("input");
    disableCheckbox.type = "checkbox";
    disableCheckbox.checked = disabled;
    disableCheckbox.addEventListener("change", () => {
      setShowDisabled(show, disableCheckbox.checked);
    });
    const disableText = document.createElement("span");
    disableText.textContent = "Disable";
    disableLabel.appendChild(disableCheckbox);
    disableLabel.appendChild(disableText);

    const select = document.createElement("select");
    select.className = "filter-select";
    [
      { val: 1, label: "Cat 1 • Watched" },
      { val: 2, label: "Cat 2 • Background" },
      { val: 3, label: "Cat 3 • Active" },
    ].forEach((opt) => {
      const o = document.createElement("option");
      o.value = String(opt.val);
      o.textContent = opt.label;
      if (cat === opt.val) o.selected = true;
      select.appendChild(o);
    });

    select.addEventListener("change", () => {
      state.categoryOverrides[show.id] = Number(select.value);
      saveCustomState();
      rebuildDeck();
    });

    const removeBtn = document.createElement("button");
    removeBtn.className = "ghost-btn";
    removeBtn.textContent = "🗑 Remove";
    removeBtn.addEventListener("click", () => {
      state.removedIds.add(show.id);
      saveCustomState();
      renderManagerList();
      rebuildDeck();
    });

    actions.appendChild(disableLabel);
    actions.appendChild(select);
    actions.appendChild(removeBtn);
    row.appendChild(left);
    row.appendChild(actions);
    listEl.appendChild(row);
  }
}

async function addShowFromBrowser(title, category, mediaType) {
  const id = normalizeId(title);
  let posterUrl = "";
  let runtimeMinutes = 30;
  let year = null;
  let genres = [];
  let seasons = [];

  try {
    const resp = await fetch(
      `https://api.tvmaze.com/singlesearch/shows?q=${encodeURIComponent(title)}&embed=episodes`
    );
    if (resp.ok) {
      const data = await resp.json();
      posterUrl = data.image?.original || data.image?.medium || "";
      runtimeMinutes = data.averageRuntime || data.runtime || 30;
      year = data.premiered ? Number(data.premiered.slice(0, 4)) : null;
      genres = data.genres || [];
      const epMap = {};
      for (const ep of data._embedded?.episodes || []) {
        if (!ep.season || !ep.number) continue;
        epMap[ep.season] = epMap[ep.season] || [];
        epMap[ep.season].push({ ep: ep.number, title: ep.name || `Episode ${ep.number}` });
      }
      seasons = Object.keys(epMap).map((s) => ({ season: Number(s), episodes: epMap[s] }));
    }
  } catch (_) {
    // Offline or not found on TVMaze
  }

  const newShow = {
    id,
    title: title.trim(),
    category: Number(category),
    watched: Number(category) === 1,
    mediaType,
    serialization: Number(category) === 3 ? "serialized" : "episodic",
    runtimeMinutes,
    year,
    genres,
    moodTags: [],
    vibe: "Added from the Manage Shows drawer.",
    categoryReason: `Assigned to Category ${category} via Manage Shows.`,
    posterUrl,
    streamingProviders: [],
    googleTvSearchUrl: `https://www.google.com/search?q=${encodeURIComponent(title + " tv show watch")}`,
    seasons,
  };

  state.removedIds.delete(id);
  state.customShows = state.customShows.filter((s) => s.id !== id);
  state.customShows.push(newShow);
  saveCustomState();
  renderManagerList();
  rebuildDeck();
}

function clearShowHash() {
  if (window.location.hash.startsWith("#show=") && window.history && window.history.replaceState) {
    window.history.replaceState(null, "", window.location.pathname + window.location.search);
  }
}

function flipNext() {
  if (state.deck.length === 0) return;
  clearShowHash();
  if (state.deckIndex + 1 < state.deck.length) {
    state.deckIndex += 1;
  } else {
    state.deck = shuffleArray(state.deck);
    state.deckIndex = 0;
  }
  renderCurrentShow();
}

function flipPrev() {
  if (state.deck.length === 0) return;
  clearShowHash();
  state.deckIndex = (state.deckIndex - 1 + state.deck.length) % state.deck.length;
  renderCurrentShow();
}

function setupEventListeners() {
  // Watch Mode tabs
  document.querySelectorAll(".mode-btn").forEach((btn) => {
    if (Number(btn.dataset.mode) === state.mode) {
      btn.classList.add("active");
    } else {
      btn.classList.remove("active");
    }

    btn.addEventListener("click", () => {
      document.querySelectorAll(".mode-btn").forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      state.mode = Number(btn.dataset.mode);
      localStorage.setItem(STORAGE_KEYS.LAST_MODE, String(state.mode));
      rebuildDeck();
    });
  });

  // Streaming service filter chips
  document.querySelectorAll("#service-filters .chip").forEach((chip) => {
    chip.addEventListener("click", () => {
      document.querySelectorAll("#service-filters .chip").forEach((c) => c.classList.remove("active"));
      chip.classList.add("active");
      state.serviceFilter = chip.dataset.service;
      rebuildDeck();
    });
  });

  // Format & Runtime selects
  const filterTypeSelect = document.getElementById("filter-type");
  if (filterTypeSelect) {
    filterTypeSelect.value = state.typeFilter;
    filterTypeSelect.addEventListener("change", (e) => {
      state.typeFilter = e.target.value;
      localStorage.setItem(STORAGE_KEYS.LAST_TYPE_FILTER, state.typeFilter);
      rebuildDeck();
    });
  }

  document.getElementById("filter-runtime").addEventListener("change", (e) => {
    state.runtimeFilter = e.target.value;
    rebuildDeck();
  });

  // Flip Channel & Prev buttons
  document.getElementById("btn-flip").addEventListener("click", flipNext);
  document.getElementById("btn-prev").addEventListener("click", flipPrev);

  // Opt-In Random Episode Roller (with 1-click Direct Episode Play buttons)
  document.getElementById("btn-roll-episode").addEventListener("click", () => {
    if (state.deck.length === 0) return;
    const show = state.deck[state.deckIndex];
    const ep = pickRandomEpisode(show);
    const epBox = document.getElementById("random-ep-box");
    const epText = document.getElementById("random-ep-text");
    const epLinksContainer = document.getElementById("random-ep-links");
    const btnHide = document.getElementById("btn-hide-episode");
    const btnRoll = document.getElementById("btn-roll-episode");

    epBox.classList.remove("hidden");
    btnHide.classList.remove("hidden");
    btnRoll.textContent = "🎲 Re-roll Random Episode";
    epLinksContainer.innerHTML = "";

    if (ep) {
      const sPad = String(ep.season).padStart(2, "0");
      const ePad = String(ep.ep).padStart(2, "0");
      const code = `S${sPad}E${ePad}`;
      epText.textContent = `Season ${ep.season}, Episode ${ep.ep} (${code}) — "${ep.title}"`;

      const providers = show.streamingProviders || [];
      const epLinks = ep.links || {};

      for (const prov of providers) {
        const directEpUrl = epLinks[prov.id];
        const card = document.createElement("div");
        card.className = "provider-card";

        if (directEpUrl) {
          // 1-Click Direct Episode Launch button
          const playLink = document.createElement("a");
          playLink.className = "provider-btn";
          playLink.style.backgroundColor = prov.color || "#6366f1";
          playLink.href = directEpUrl;
          playLink.target = "_blank";
          playLink.rel = "noopener noreferrer";
          playLink.textContent = `▶ Play ${code} on ${prov.name}`;
          card.appendChild(playLink);

          const tvIntent = buildAndroidTvIntent(directEpUrl, prov.id);
          if (tvIntent) {
            const tvBtn = document.createElement("a");
            tvBtn.className = "provider-btn secondary-link";
            tvBtn.href = tvIntent;
            tvBtn.textContent = `📺 ${prov.name} TV App (${code})`;
            card.appendChild(tvBtn);
          }
        } else {
          // Fallback when a service (e.g. Netflix) only exposes series-level URLs publicly
          const seriesFallback = document.createElement("a");
          seriesFallback.className = "provider-btn secondary-link";
          seriesFallback.href = prov.webUrl;
          seriesFallback.target = "_blank";
          seriesFallback.rel = "noopener noreferrer";
          seriesFallback.textContent = `↗ Open ${prov.name} Series Page (${code})`;
          card.appendChild(seriesFallback);
        }

        epLinksContainer.appendChild(card);
      }
    } else {
      epText.textContent = "Episode list not cached for this title yet.";
    }
  });

  document.getElementById("btn-hide-episode").addEventListener("click", () => {
    document.getElementById("random-ep-box").classList.add("hidden");
    document.getElementById("btn-hide-episode").classList.add("hidden");
    document.getElementById("btn-roll-episode").textContent = "🎲 Roll Random Episode (Optional)";
  });

  // Promote to Watched (Cat 1)
  document.getElementById("btn-promote-watched").addEventListener("click", () => {
    if (state.deck.length === 0) return;
    const show = state.deck[state.deckIndex];
    state.categoryOverrides[show.id] = 1;
    saveCustomState();
    renderCurrentShow();
  });

  // Snooze show for tonight
  document.getElementById("btn-snooze").addEventListener("click", () => {
    if (state.deck.length === 0) return;
    const show = state.deck[state.deckIndex];
    state.snoozedIds.add(show.id);
    localStorage.setItem(
      STORAGE_KEYS.SNOOZED_IDS,
      JSON.stringify([...state.snoozedIds])
    );
    rebuildDeck();
  });

  // Disable / Enable current show (keep on list, exclude from active database)
  document.getElementById("btn-disable-current")?.addEventListener("click", () => {
    if (state.deck.length === 0) return;
    const show = state.deck[state.deckIndex];
    const nextDisabled = !isShowDisabled(show);
    setShowDisabled(show, nextDisabled);
  });

  // Reset snoozed
  document.getElementById("btn-reset-snooze").addEventListener("click", () => {
    state.snoozedIds.clear();
    localStorage.removeItem(STORAGE_KEYS.SNOOZED_IDS);
    rebuildDeck();
  });

  // Manage Shows Modal
  const modal = document.getElementById("manager-modal");
  document.getElementById("btn-open-manager").addEventListener("click", () => {
    renderManagerList();
    modal.classList.remove("hidden");
  });

  document.getElementById("btn-close-manager").addEventListener("click", () => {
    modal.classList.add("hidden");
  });

  document.getElementById("manager-search").addEventListener("input", renderManagerList);
  document.getElementById("manager-status-filter")?.addEventListener("change", renderManagerList);

  document.getElementById("form-add-show").addEventListener("submit", async (e) => {
    e.preventDefault();
    const titleInput = document.getElementById("input-show-title");
    const catSelect = document.getElementById("input-show-category");
    const typeSelect = document.getElementById("input-show-type");
    if (!titleInput.value.trim()) return;
    await addShowFromBrowser(titleInput.value.trim(), catSelect.value, typeSelect.value);
    titleInput.value = "";
  });

  document.getElementById("btn-export-json").addEventListener("click", async () => {
    const exported = buildShowsSourcePayload();
    await navigator.clipboard.writeText(JSON.stringify(exported, null, 2));
    const btn = document.getElementById("btn-export-json");
    btn.textContent = "✓ Copied shows_source.json!";
    setTimeout(() => {
      btn.textContent = "📋 Copy JSON";
    }, 2000);
  });

  // GitHub Cloud Sync Config & Save Button
  const ghConfigPanel = document.getElementById("gh-config-panel");
  const inputGhRepo = document.getElementById("input-gh-repo");
  const inputGhToken = document.getElementById("input-gh-token");
  const savedRepo = localStorage.getItem(STORAGE_KEYS.GH_REPO) || "bmercado-1/randomflix";
  const savedToken = localStorage.getItem(STORAGE_KEYS.GH_TOKEN) || "";
  inputGhRepo.value = savedRepo;
  inputGhToken.value = savedToken;

  document.getElementById("btn-toggle-gh-config").addEventListener("click", () => {
    ghConfigPanel.classList.toggle("hidden");
  });

  document.getElementById("btn-save-gh-config").addEventListener("click", async () => {
    const repo = inputGhRepo.value.trim() || "bmercado-1/randomflix";
    const token = inputGhToken.value.trim();
    localStorage.setItem(STORAGE_KEYS.GH_REPO, repo);
    if (!token) {
      showSyncStatus("Please paste a valid GitHub Personal Access Token.", true);
      return;
    }
    localStorage.setItem(STORAGE_KEYS.GH_TOKEN, token);
    showSyncStatus("⏳ Verifying token write permissions on GitHub...", false);
    try {
      const resp = await fetch(`https://api.github.com/repos/${repo}`, {
        headers: {
          Accept: "application/vnd.github+json",
          Authorization: `Bearer ${token}`,
          "X-GitHub-Api-Version": "2022-11-28",
        },
        cache: "no-store",
      });
      const repoData = await resp.json().catch(() => ({}));
      if (!resp.ok) {
        showSyncStatus(
          `⚠️ Token check failed (${resp.status}): ${repoData.message || "Invalid token"}.`,
          true
        );
        return;
      }
      if (repoData.permissions && repoData.permissions.push === false) {
        showSyncStatus(
          `⚠️ <strong>This token is Read-Only!</strong> GitHub Fine-Grained tokens default to "Public Repositories (read-only)". Either click <a href="https://github.com/settings/tokens/new?description=RandomFlix+Sync&amp;scopes=public_repo" target="_blank" rel="noopener noreferrer" class="gh-help-link">⚡ 1-Click Pre-Filled Token (public_repo)</a> or edit your Fine-Grained token to select <code>${repo}</code> and set <strong>Repository permissions → Contents → Read and write</strong>.`,
          true
        );
        return;
      }
      showSyncStatus(
        `✅ <strong>GitHub Token verified with Write access to <code>${repo}</code>!</strong> Ready for 1-tap sync.`,
        false
      );
      ghConfigPanel.classList.add("hidden");
    } catch (err) {
      showSyncStatus("✓ GitHub Token saved locally on this device.", false);
      ghConfigPanel.classList.add("hidden");
    }
  });

  document.getElementById("btn-clear-gh-config").addEventListener("click", () => {
    localStorage.removeItem(STORAGE_KEYS.GH_TOKEN);
    inputGhToken.value = "";
    showSyncStatus("Cleared saved GitHub Token from this browser.", false);
  });

  document.getElementById("btn-save-local")?.addEventListener("click", saveLocally);
  document.getElementById("btn-sync-github").addEventListener("click", syncToGitHub);
  document.getElementById("btn-discard-changes")?.addEventListener("click", discardAllUnsavedChanges);

  // Keyboard / TV Remote shortcuts (Right Arrow / Space = Flip, Left Arrow = Prev)
  window.addEventListener("keydown", (e) => {
    if (!modal.classList.contains("hidden")) return;
    if (["INPUT", "SELECT", "TEXTAREA"].includes(document.activeElement?.tagName)) return;
    if (e.key === "ArrowRight" || e.key === " ") {
      e.preventDefault();
      flipNext();
    } else if (e.key === "ArrowLeft") {
      e.preventDefault();
      flipPrev();
    }
  });
}

function showSyncStatus(messageHtml, isError = false) {
  const statusEl = document.getElementById("gh-sync-status");
  if (!statusEl) return;
  statusEl.classList.remove("hidden");
  statusEl.classList.toggle("error", Boolean(isError));
  statusEl.innerHTML = messageHtml;
}

function encodeUtf8Base64(text) {
  const bytes = new TextEncoder().encode(text);
  let binary = "";
  for (let i = 0; i < bytes.length; i++) {
    binary += String.fromCharCode(bytes[i]);
  }
  return btoa(binary);
}

async function saveLocally() {
  const btn = document.getElementById("btn-save-local");
  if (!btn) return;
  const originalLabel = btn.textContent;
  btn.disabled = true;
  btn.textContent = "⏳ Saving & Enriching...";
  showSyncStatus(
    "⏳ Writing <code>data/shows_source.json</code> to disk and running <code>scripts/enrich_catalog.py</code> locally...",
    false
  );

  try {
    const payloadObj = buildShowsSourcePayload();
    const resp = await fetch("/api/save-local", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payloadObj),
    });
    const data = await resp.json().catch(() => ({}));
    if (!resp.ok || !data.ok) {
      throw new Error(
        data.error ||
          "Local save endpoint unavailable. Make sure scripts/dev_server.py is running."
      );
    }

    await loadCatalog(false);
    const disCount = data.disabledShows || 0;
    const countSummary =
      disCount > 0
        ? `${data.totalShows} active in DB, ${disCount} disabled`
        : `${data.totalShows} shows`;
    showSyncStatus(
      `✅ <strong>Saved &amp; enriched locally!</strong> Updated <code>data/shows_source.json</code> and <code>docs/data/catalog.json</code> (${countSummary}) directly on your Mac.`,
      false
    );
  } catch (err) {
    showSyncStatus(`⚠️ Local Save Error: ${err.message}`, true);
  } finally {
    btn.disabled = false;
    btn.textContent = originalLabel;
    updateUnsavedBadges();
  }
}

async function syncToGitHub() {
  const repo = (localStorage.getItem(STORAGE_KEYS.GH_REPO) || "bmercado-1/randomflix").trim();
  const token = (localStorage.getItem(STORAGE_KEYS.GH_TOKEN) || "").trim();
  const ghConfigPanel = document.getElementById("gh-config-panel");

  if (!token) {
    ghConfigPanel.classList.remove("hidden");
    document.getElementById("input-gh-token")?.focus();
    showSyncStatus(
      "🔑 First-time setup: Paste a GitHub Personal Access Token (with <code>Contents: Read &amp; Write</code> on <code>" +
        repo +
        "</code>) above, click <strong>Save Token</strong>, then tap <strong>Save &amp; Sync to GitHub</strong>.",
      false
    );
    return;
  }

  const syncBtn = document.getElementById("btn-sync-github");
  const originalLabel = syncBtn.textContent;
  syncBtn.disabled = true;
  syncBtn.textContent = "⏳ Syncing to GitHub...";
  showSyncStatus("⏳ Committing updated <code>data/shows_source.json</code> to GitHub...", false);

  try {
    const apiUrl = `https://api.github.com/repos/${repo}/contents/data/shows_source.json`;
    const headers = {
      Accept: "application/vnd.github+json",
      Authorization: `Bearer ${token}`,
      "X-GitHub-Api-Version": "2022-11-28",
    };

    // 1. Fetch current file SHA on main
    const getResp = await fetch(`${apiUrl}?ref=main`, {
      headers,
      cache: "no-store",
    });
    if (!getResp.ok) {
      const errBody = await getResp.json().catch(() => ({}));
      throw new Error(
        errBody.message || `GitHub GET failed (${getResp.status}) — verify your token and repo.`
      );
    }
    const currentFile = await getResp.json();

    // 2. Build clean shows_source.json payload and PUT commit to main
    const payloadObj = buildShowsSourcePayload();
    const jsonString = JSON.stringify(payloadObj, null, 2) + "\n";
    const putResp = await fetch(apiUrl, {
      method: "PUT",
      headers: {
        ...headers,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        message: `chore(shows): update show rotation (${payloadObj.shows.length} shows) via RandomFlix web app`,
        content: encodeUtf8Base64(jsonString),
        sha: currentFile.sha,
        branch: "main",
      }),
    });

    if (!putResp.ok) {
      const errBody = await putResp.json().catch(() => ({}));
      throw new Error(errBody.message || `GitHub PUT failed (${putResp.status})`);
    }

    showSyncStatus(
      `<span>✅ <strong>Synced to GitHub!</strong> GitHub Actions is now enriching streaming &amp; episode links (~20s).</span>
       <div style="display:flex;gap:8px;align-items:center;">
         <a href="https://github.com/${repo}/actions" target="_blank" rel="noopener noreferrer" class="gh-help-link">↗ View Action</a>
         <button type="button" id="btn-reload-catalog-now" class="secondary-btn" style="padding:5px 10px;font-size:0.8rem;">🔄 Reload Catalog</button>
       </div>`,
      false
    );

    document
      .getElementById("btn-reload-catalog-now")
      ?.addEventListener("click", () => loadCatalog(true));
  } catch (err) {
    if (String(err.message).toLowerCase().includes("resource not accessible by personal access token")) {
      ghConfigPanel.classList.remove("hidden");
      showSyncStatus(
        `⚠️ <strong>Token lacks Write permission on <code>${repo}</code>!</strong><br/>
         GitHub Fine-Grained tokens default to <em>"Public Repositories (read-only)"</em>. To fix in 5 seconds: click <a href="https://github.com/settings/tokens/new?description=RandomFlix+Sync&amp;scopes=public_repo" target="_blank" rel="noopener noreferrer" class="gh-help-link">⚡ 1-Click Pre-Filled Token (public_repo pre-checked)</a>, scroll down &amp; click <strong>Generate token</strong>, then paste it above. (Or edit your Fine-Grained token to select <code>${repo}</code> and set <strong>Repository permissions → Contents → Read and write</strong>.)`,
        true
      );
    } else {
      showSyncStatus(`⚠️ GitHub Sync Error: ${err.message}`, true);
    }
  } finally {
    syncBtn.disabled = false;
    syncBtn.textContent = originalLabel;
    updateUnsavedBadges();
  }
}

async function loadCatalog(showToast = false) {
  try {
    const initialHash = window.location.hash;
    const resp = await fetch(`data/catalog.json?t=${Date.now()}`, { cache: "no-store" });
    const data = await resp.json();
    state.baseCatalog = data.shows || [];
    reconcileLocalStateWithCatalog();
    rebuildDeck();
    applyHashShowIfPresent(initialHash);
    renderManagerList();
    if (showToast) {
      showSyncStatus(
        `✅ Reloaded latest enriched catalog (${state.baseCatalog.length} shows).`,
        false
      );
    }
  } catch (err) {
    document.getElementById("show-title").textContent = "Ready to Seed Your Rotation";
    document.getElementById("show-vibe").textContent =
      "Run scripts/enrich_catalog.py to populate docs/data/catalog.json.";
  }
}

async function init() {
  setupEventListeners();
  window.addEventListener("hashchange", applyHashShowIfPresent);
  if (window.location.hostname.endsWith("github.io")) {
    document.getElementById("btn-save-local")?.classList.add("hidden");
  }
  await loadCatalog(false);
}

init();
