#!/usr/bin/env python3
"""
Helper CLI to list, add, or update shows in `data/shows_source.json`
and inspect `legacy/shows.csv`.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

from enrich_catalog import (
    CATALOG_OUT_PATH,
    LEGACY_CSV_PATH,
    SOURCE_PATH,
    enrich_all,
    load_legacy_csv_lookup,
    normalize_title_key,
)


def summarize_catalog() -> None:
    if not CATALOG_OUT_PATH.exists():
        print("Catalog not generated yet. Run python3 scripts/enrich_catalog.py first.")
        return
    data = json.loads(CATALOG_OUT_PATH.read_text(encoding="utf-8"))
    for i, s in enumerate(data.get("shows", []), 1):
        provs = ", ".join(p["name"] for p in s.get("streamingProviders", [])) or "None found"
        title = s["title"]
        mtype = s["mediaType"]
        rt = s.get("runtimeMinutes") or 30
        seasons = s.get("totalSeasons", 0)
        eps = s.get("totalEpisodes", 0)
        status = "DISABLED" if s.get("disabled") else "ACTIVE  "
        print(f"{i:2d}. {title:36s} | {status} | Cat {s['category']} | {mtype:5s} | {rt:2d}m | {seasons:2d}S/{eps:3d}E | {provs}")


def load_source() -> dict[str, Any]:
    if not SOURCE_PATH.exists():
        return {"shows": []}
    return json.loads(SOURCE_PATH.read_text(encoding="utf-8"))


def save_source(data: dict[str, Any]) -> None:
    SOURCE_PATH.parent.mkdir(parents=True, exist_ok=True)
    SOURCE_PATH.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def list_shows() -> None:
    data = load_source()
    shows = data.get("shows", [])
    if not shows:
        print("No shows in data/shows_source.json yet.")
        return
    for i, s in enumerate(shows, 1):
        cat = s.get("category", "?")
        watched = "Watched" if s.get("watched") or cat == 1 else "Unwatched"
        disabled_tag = " | 🚫 DISABLED" if s.get("disabled") else ""
        print(f"{i:2d}. {s['title']} [Cat {cat} | {watched}{disabled_tag}] — {s.get('vibe', '')}")


def set_show_disabled(title: str, disabled: bool) -> None:
    data = load_source()
    shows: list[dict[str, Any]] = data.get("shows", [])
    key = normalize_title_key(title)
    existing = next((s for s in shows if normalize_title_key(s["title"]) == key), None)
    if existing is None:
        print(f"Show '{title}' not found in {SOURCE_PATH}.")
        return
    if disabled:
        existing["disabled"] = True
        print(f"Disabled '{existing['title']}' in {SOURCE_PATH} (kept on list, excluded from active database).")
    else:
        existing.pop("disabled", None)
        print(f"Enabled '{existing['title']}' in {SOURCE_PATH}.")
    save_source(data)


def add_show(
    title: str,
    watched: bool = False,
    category: int | None = None,
    vibe: str | None = None,
    category_reason: str | None = None,
    media_type: str | None = None,
    mood_tags: list[str] | None = None,
    disabled: bool | None = None,
) -> None:
    data = load_source()
    shows: list[dict[str, Any]] = data.setdefault("shows", [])
    key = normalize_title_key(title)

    existing = next((s for s in shows if normalize_title_key(s["title"]) == key), None)
    entry: dict[str, Any] = existing if existing is not None else {"title": title}

    entry["title"] = title
    entry["watched"] = watched or (category == 1)
    if category is not None:
        entry["category"] = category
    if vibe:
        entry["vibe"] = vibe
    if category_reason:
        entry["categoryReason"] = category_reason
    if media_type:
        entry["mediaType"] = media_type
    if mood_tags:
        entry["moodTags"] = mood_tags
    if disabled is True:
        entry["disabled"] = True
    elif disabled is False:
        entry.pop("disabled", None)

    if existing is None:
        shows.append(entry)
        print(f"Added '{title}' to {SOURCE_PATH}")
    else:
        print(f"Updated '{title}' in {SOURCE_PATH}")

    save_source(data)


DEFAULT_LIVECHART_PATH = Path("/Users/bmercado/dev/workspace/random/anime_watchlist.json")

LIVECHART_BUCKET_TAGS = {
    "LiveChart Now Watching",
    "LiveChart Primary",
    "LiveChart Completed",
    "LiveChart Considering",
}

LIVECHART_FORCE_MOVIE_TITLES: set[str] = {
    # LiveChart records 3 episodes for its 3 chapters, though it is a 63m theatrical feature film
    "5 Centimeters Per Second",
}

LIVECHART_SEQUEL_TO_BASE: dict[str, str] = {
    "Mob Psycho 100": "Mob Psycho 100",
    "Blue Box": "Blue Box",
    "SAKAMOTO DAYS": "Sakamoto Days",
    "MASHLE: MAGIC AND MUSCLES": "Mashle: Magic and Muscles",
    "The Eminence in Shadow 2nd Season": "The Eminence in Shadow",
    "Kaguya-sama: Love Is War -Stairway to Adulthood-": "Kaguya-sama: Love Is War",
    "Kaguya-sama: Love Is War -Ultra Romantic-": "Kaguya-sama: Love Is War",
    "Kaguya-sama: Love Is War -The First Kiss That Never Ends-": "Kaguya-sama: Love Is War",
    "KONOSUBA -God's blessing on this wonderful world! 2": "KONOSUBA -God's blessing on this wonderful world!",
    "KONOSUBA -God's blessing on this wonderful world!: God's Blessings On This Wonderful Choker!": "KONOSUBA -God's blessing on this wonderful world!",
    "Clevatess II": "Clevatess",
    "Real Girl 2nd Season": "3D Kanojo: Real Girl",
    "My Happy Marriage Season 2": "My Happy Marriage",
    "My Happy Marriage Special Episodes": "My Happy Marriage",
    "My Happy Marriage Episode 13": "My Happy Marriage",
    "Kamisama Kiss OVA": "Kamisama Kiss",
    "Is It Wrong to Try to Pick Up Girls in a Dungeon? II": "Is It Wrong to Try to Pick Up Girls in a Dungeon?",
    "Is It Wrong to Expect a Hot Spring in a Dungeon?": "Is It Wrong to Try to Pick Up Girls in a Dungeon?",
    "Trapped in a Dating Sim: The World of Otome Games is Tough for Mobs Season 2": "Trapped in a Dating Sim: The World of Otome Games is Tough for Mobs",
    "Science Fell in Love, So I Tried to Prove It r=1-sinθ": "Science Fell in Love, So I Tried to Prove It",
    "Tsukimonogatari": "Bakemonogatari",
    "Monogatari Second Season": "Bakemonogatari",
    "Nisemonogatari": "Bakemonogatari",
    "Nekomonogatari Black": "Bakemonogatari",
    "Hanamonogatari": "Bakemonogatari",
    "Demon Slayer: Kimetsu no Yaiba": "Demon Slayer: Kimetsu no Yaiba",
    "Food Wars! Shokugeki no Soma": "Food Wars! Shokugeki no Soma",
    "JUJUTSU KAISEN Season 2": "Jujutsu Kaisen",
    "Ascendance of a Bookworm OVA": "Ascendance of a Bookworm",
    "Nisekoi:": "Nisekoi",
    "Room Camp": "Laid-Back Camp",
    "Amagami SS+ Plus": "Amagami SS",
    "Amagami SS+ Plus Specials": "Amagami SS",
    "Amagami SS: Little Sister": "Amagami SS",
    "Clannad ~After Story~": "Clannad",
    "Clannad: Another World, Tomoyo Arc": "Clannad",
    "Clannad: After Story - Another World, Kyou Arc": "Clannad",
    "Fruits Basket Season One": "Fruits Basket (2019)",
    "Fruits Basket Season Two": "Fruits Basket (2019)",
    "Fruits Basket The Final Season": "Fruits Basket (2019)",
    "My Teen Romantic Comedy SNAFU TOO!": "My Teen Romantic Comedy SNAFU",
    "My Teen Romantic Comedy SNAFU Climax": "My Teen Romantic Comedy SNAFU",
    "My Teen Romantic Comedy SNAFU TOO!: Undoubtedly, Girls Are Made of Sugar, Spice, and Everything Nice": "My Teen Romantic Comedy SNAFU",
    "My Teen Romantic Comedy SNAFU: There's No Choice But To Wish Them Happiness Right Here As They Arrive At Their Destiny.": "My Teen Romantic Comedy SNAFU",
    "Yahari Ore no Seishun Love Comedy wa Machigatteiru. Kan: Dakara, Shishunki wa Owarazu ni, Seishun wa Tsuzuiteiku.": "My Teen Romantic Comedy SNAFU",
    "The Angel Next Door Spoils Me Rotten2": "The Angel Next Door Spoils Me Rotten",
    "Horimiya: The Missing Pieces": "Horimiya",
    "Rascal Does Not Dream of Santa Claus": "Rascal Does Not Dream of Bunny Girl Senpai",
    "ReLIFE: Final Arc": "ReLIFE",
    "TONIKAWA: Over The Moon For You ~High School Days~": "TONIKAWA: Over the Moon for You",
    "TONIKAWA: Over The Moon For You ~SNS~": "TONIKAWA: Over the Moon for You",
    "TONIKAWA: Over The Moon For You ~Uniform~": "TONIKAWA: Over the Moon for You",
    "Mushoku Tensei: Jobless Reincarnation: Eris the Goblin Slayer": "Mushoku Tensei: Jobless Reincarnation",
    "Mushoku Tensei: Jobless Reincarnation Season 2: Guardian Fitz": "Mushoku Tensei: Jobless Reincarnation",
    "There's No Freaking Way I'll be Your Lover! Unless... ~Next Shine~": "There's No Freaking Way I'll be Your Lover! Unless...",
    "The Dangers in My Heart: Twi-Yaba": "The Dangers in My Heart",
    "Masamune-kun's Revenge R": "Masamune-kun's Revenge",
    "Love, Chunibyo & Other Delusions!: Heart Throb": "Love, Chunibyo & Other Delusions!",
    "Love, Chunibyo & Other Delusions Lite": "Love, Chunibyo & Other Delusions!",
    "Love, Chunibyo & Other Delusions!: Sparkling... Slapstick Noel": "Love, Chunibyo & Other Delusions!",
    "Love, Chunibyo & Other Delusions!: Heart Throb - The Rikka Wars": "Love, Chunibyo & Other Delusions!",
    "Maid-Sama! It's an extra!": "Maid-Sama!",
    "Hyouka: Motsubeki Mono wa": "Hyouka",
    "Toradora!: Bento Battle": "Toradora!",
    "Toradora! SOS! Hooray for Foodies": "Toradora!",
    "Re:ZERO ~Starting Break Time From Zero~": "Re:ZERO -Starting Life in Another World-",
    "Re:ZERO ~Starting Break Time From Zero~ 2nd Season": "Re:ZERO -Starting Life in Another World-",
    "Re:ZERO ~Starting Break Time From Zero~ 2nd Season Part 2": "Re:ZERO -Starting Life in Another World-",
    "Re:ZERO ~Starting Break Time From Zero~ 3rd Season": "Re:ZERO -Starting Life in Another World-",
    "Re:ZERO PETIT": "Re:ZERO -Starting Life in Another World-",
}

LIVECHART_TITLE_NORMALIZATIONS: dict[str, str] = {
    "Ranma1/2": "Ranma 1/2 (2024)",
    "Spice and Wolf": "Spice and Wolf (2008)",
    "Spice and Wolf: MERCHANT MEETS THE WISE WOLF": "Spice and Wolf: Merchant Meets the Wise Wolf",
    "Aharen-san wa Hakarenai": "Aharen-san Is Indecipherable",
    "Real Girl": "3D Kanojo: Real Girl",
    "Love, Election & Chocolate": "Love, Election and Chocolate",
    "Wasteful Days of High School Girl": "Wasteful Days of High School Girls",
    "Sword Oratoria": "Sword Oratoria: Is It Wrong to Try to Pick Up Girls in a Dungeon? On the Side",
    "Cyberpunk: Edgerunners 2": "Cyberpunk: Edgerunners",
    "Shakugan no Shana: Season I": "Shakugan no Shana",
    "Momokuri (TV)": "Momokuri",
    "Kiss × Sis (TV)": "Kiss x Sis",
    "your name.": "Your Name.",
    "Kase-san and Morning Glories (OVA)": "Kase-san and Morning Glories",
}

LIVECHART_PINNED_YEARS: dict[str, int] = {
    "Ranma 1/2 (2024)": 2024,
    "Spice and Wolf (2008)": 2008,
    "Spice and Wolf: Merchant Meets the Wise Wolf": 2024,
    "Fruits Basket (2019)": 2019,
    "Fate/stay night": 2006,
    "Fate/stay night: Unlimited Blade Works (2010)": 2010,
}

SEQUEL_SUFFIX_RE = re.compile(
    r"(?:\s*[:~-]\s*|\s+)(?:Season\s*\d+(?:\s+Part\s*\d+)?|\d+(?:st|nd|rd|th)\s+Season(?:\s+Part\s*\d+)?|Part\s*\d+|Cour\s*\d+|Specials?(?:\s*\d+)?|OVA(?:\s*\d+)?|Episode\s*\d+|Director's\s+Cut|The\s+Final\s+Season|Mini|II|III|IV|[2-9])\s*$",
    re.IGNORECASE,
)

OVA_SPECIAL_SUFFIX_RE = re.compile(
    r"(?:\s*[:~-]\s*|\s+)(?:Specials?(?:\s*\d+)?|OVA(?:\s*\d+)?|Episode\s*\d+)\s*$",
    re.IGNORECASE,
)


def _update_livechart_tag(
    entry: dict[str, Any],
    bucket_tag: str | None,
    default_media_tag: str,
) -> None:
    existing_tags = list(entry.get("moodTags") or [])
    cleaned = [t for t in existing_tags if t not in LIVECHART_BUCKET_TAGS]
    if not cleaned and default_media_tag:
        cleaned.append(default_media_tag)
    if bucket_tag and bucket_tag not in cleaned:
        cleaned.append(bucket_tag)
    entry["moodTags"] = cleaned


def _apply_pinned_year(entry: dict[str, Any], title: str) -> None:
    pinned = LIVECHART_PINNED_YEARS.get(title)
    if pinned and "year" not in entry:
        entry["year"] = pinned


def import_livechart(watchlist_path: Path = DEFAULT_LIVECHART_PATH) -> dict[str, Any]:
    if not watchlist_path.exists():
        raise FileNotFoundError(f"LiveChart watchlist not found: {watchlist_path}")

    wl = json.loads(watchlist_path.read_text(encoding="utf-8"))
    data = load_source()
    shows: list[dict[str, Any]] = data.setdefault("shows", [])
    by_key: dict[str, dict[str, Any]] = {
        normalize_title_key(s["title"]): s for s in shows
    }

    known_base_titles: dict[str, str] = {
        normalize_title_key(s["title"]): s["title"] for s in shows
    }
    for bucket in ("now_watching", "primary", "completed", "secondary"):
        for it in wl.get(bucket, []):
            rt = (it.get("title") or "").strip()
            if rt:
                nt = LIVECHART_TITLE_NORMALIZATIONS.get(rt, rt)
                known_base_titles.setdefault(normalize_title_key(nt), nt)

    def resolve_item(item: dict[str, Any]) -> tuple[str, bool]:
        raw_title = (item.get("title") or "").strip()
        eps = item.get("total_episodes")

        if raw_title in LIVECHART_SEQUEL_TO_BASE:
            base = LIVECHART_SEQUEL_TO_BASE[raw_title]
            return LIVECHART_TITLE_NORMALIZATIONS.get(base, base), False

        # Disambiguate 2010 Studio Deen film from 2014 ufotable TV series
        if raw_title == "Fate/stay night: Unlimited Blade Works" and eps == 1:
            return "Fate/stay night: Unlimited Blade Works (2010)", True

        if raw_title in LIVECHART_FORCE_MOVIE_TITLES:
            mapped_movie = LIVECHART_TITLE_NORMALIZATIONS.get(raw_title, raw_title)
            return mapped_movie, True

        # Collapse multi-episode seasons/cours/OVAs or 1-episode bonus OVAs/Specials onto known base series
        can_collapse = eps != 1 or bool(OVA_SPECIAL_SUFFIX_RE.search(raw_title))
        if can_collapse:
            stripped = SEQUEL_SUFFIX_RE.sub("", raw_title).strip()
            if stripped and stripped != raw_title:
                mapped_stripped = LIVECHART_SEQUEL_TO_BASE.get(
                    stripped, LIVECHART_TITLE_NORMALIZATIONS.get(stripped, stripped)
                )
                stripped_key = normalize_title_key(mapped_stripped)
                if stripped_key in known_base_titles and normalize_title_key(raw_title) not in by_key:
                    return known_base_titles[stripped_key], False

        is_movie = eps == 1
        mapped = LIVECHART_TITLE_NORMALIZATIONS.get(raw_title, raw_title)
        return mapped, is_movie

    claimed_keys: set[str] = set()

    promoted_now_watching: list[str] = []
    added_now_watching_series = 0
    added_now_watching_movies = 0

    promoted_primary: list[str] = []
    added_primary_series = 0
    added_primary_movies = 0

    graduated_completed: list[str] = []
    preserved_completed = 0
    added_completed_series = 0
    added_completed_movies = 0

    demoted_secondary: list[str] = []
    added_secondary_series = 0
    added_secondary_movies = 0

    disabled_dropped: list[str] = []
    skipped_duplicates = 0

    # 1. Process Now Watching (watching, rewatching) -> Category 4, Enabled
    for item in wl.get("now_watching", []):
        raw_title = (item.get("title") or "").strip()
        if not raw_title:
            continue
        status = item.get("status") or "watching"
        release_state = item.get("release_state")
        release_note = f", {release_state.lower()}" if release_state else ""

        title, is_movie = resolve_item(item)
        key = normalize_title_key(title)
        if key in claimed_keys:
            skipped_duplicates += 1
            continue
        claimed_keys.add(key)

        media_type = "anime_movie" if is_movie else "anime"
        media_tag = "Anime Movie" if is_movie else "Anime"

        if key in by_key:
            existing = by_key[key]
            was_cat4_active = existing.get("category") == 4 and not existing.get("disabled")
            was_watched = (status == "rewatching") or bool(existing.get("watched"))
            existing["watched"] = was_watched
            existing["category"] = 4
            existing.pop("disabled", None)
            existing["serialization"] = "now-watching"
            existing["categoryReason"] = (
                f"Currently {status} on LiveChart ({raw_title}{release_note}) — active in Now Watching."
            )
            _update_livechart_tag(existing, "LiveChart Now Watching", media_tag)
            _apply_pinned_year(existing, existing["title"])
            if not was_cat4_active and existing["title"] not in promoted_now_watching:
                promoted_now_watching.append(existing["title"])
        else:
            entry: dict[str, Any] = {
                "title": title,
                "watched": status == "rewatching",
                "category": 4,
                "mediaType": media_type,
                "serialization": "now-watching",
                "categoryReason": (
                    f"Currently {status} on LiveChart ({raw_title}{release_note}) — active in Now Watching."
                ),
                "moodTags": [media_tag, "LiveChart Now Watching"],
            }
            _apply_pinned_year(entry, title)
            shows.append(entry)
            by_key[key] = entry
            if is_movie:
                added_now_watching_movies += 1
            else:
                added_now_watching_series += 1

    # 2. Process Primary (planning, paused, skipping) -> Category 3, Enabled
    for item in wl.get("primary", []):
        raw_title = (item.get("title") or "").strip()
        if not raw_title:
            continue
        status = item.get("status") or "planning"

        title, is_movie = resolve_item(item)
        key = normalize_title_key(title)
        if key in claimed_keys:
            skipped_duplicates += 1
            continue
        claimed_keys.add(key)

        media_type = "anime_movie" if is_movie else "anime"
        media_tag = "Anime Movie" if is_movie else "Anime"

        if key in by_key:
            existing = by_key[key]
            was_cat3_active = existing.get("category") == 3 and not existing.get("disabled")
            existing["watched"] = False
            existing["category"] = 3
            existing.pop("disabled", None)
            existing["serialization"] = "serialized"
            existing["categoryReason"] = (
                f"In LiveChart Primary queue ({raw_title} — {status}) — surfaced in Active Focus."
            )
            _update_livechart_tag(existing, "LiveChart Primary", media_tag)
            _apply_pinned_year(existing, existing["title"])
            if not was_cat3_active and existing["title"] not in promoted_primary:
                promoted_primary.append(existing["title"])
        else:
            reason = (
                f"LiveChart Primary queue ({status} — feature film/special)."
                if is_movie
                else f"LiveChart Primary queue ({status})."
            )
            entry = {
                "title": title,
                "watched": False,
                "category": 3,
                "mediaType": media_type,
                "serialization": "serialized",
                "categoryReason": reason,
                "moodTags": [media_tag, "LiveChart Primary"],
            }
            _apply_pinned_year(entry, title)
            shows.append(entry)
            by_key[key] = entry
            if is_movie:
                added_primary_movies += 1
            else:
                added_primary_series += 1

    # 3. Process Completed (completed) -> Category 1, Disabled by default for new/graduated entries
    for item in wl.get("completed", []):
        raw_title = (item.get("title") or "").strip()
        if not raw_title:
            continue

        title, is_movie = resolve_item(item)
        key = normalize_title_key(title)
        if key in claimed_keys:
            skipped_duplicates += 1
            continue
        claimed_keys.add(key)

        media_type = "anime_movie" if is_movie else "anime"
        media_tag = "Anime Movie" if is_movie else "Anime"

        if key in by_key:
            existing = by_key[key]
            if existing.get("category") == 1:
                # Preserve existing Category 1 enabled/disabled selection
                existing["watched"] = True
                _apply_pinned_year(existing, existing["title"])
                preserved_completed += 1
            else:
                existing["watched"] = True
                existing["category"] = 1
                existing["disabled"] = True
                existing["serialization"] = "watched-comfort"
                existing["categoryReason"] = (
                    f"Completed on LiveChart ({raw_title}) — seeded into Comfort Rewatch (disabled until enabled)."
                )
                _update_livechart_tag(existing, "LiveChart Completed", media_tag)
                _apply_pinned_year(existing, existing["title"])
                if existing["title"] not in graduated_completed:
                    graduated_completed.append(existing["title"])
        else:
            reason = (
                "Completed on LiveChart (feature film/special) — disabled by default until enabled for Comfort Rewatch."
                if is_movie
                else "Completed on LiveChart — disabled by default until enabled for Comfort Rewatch."
            )
            entry = {
                "title": title,
                "disabled": True,
                "watched": True,
                "category": 1,
                "mediaType": media_type,
                "serialization": "watched-comfort",
                "categoryReason": reason,
                "moodTags": [media_tag, "LiveChart Completed"],
            }
            _apply_pinned_year(entry, title)
            shows.append(entry)
            by_key[key] = entry
            if is_movie:
                added_completed_movies += 1
            else:
                added_completed_series += 1

    # 4. Process Secondary (considering) -> Category 3, Disabled
    for item in wl.get("secondary", []):
        raw_title = (item.get("title") or "").strip()
        if not raw_title:
            continue

        title, is_movie = resolve_item(item)
        key = normalize_title_key(title)
        if key in claimed_keys:
            skipped_duplicates += 1
            continue
        claimed_keys.add(key)

        media_type = "anime_movie" if is_movie else "anime"
        media_tag = "Anime Movie" if is_movie else "Anime"

        if key in by_key:
            existing = by_key[key]
            tags = existing.get("moodTags") or []
            if (
                ("LiveChart Now Watching" in tags or "LiveChart Primary" in tags)
                and (existing.get("category") != 3 or not existing.get("disabled"))
            ):
                existing["disabled"] = True
                existing["watched"] = False
                existing["category"] = 3
                existing["serialization"] = "serialized"
                existing["categoryReason"] = (
                    f"Moved to LiveChart Secondary backlog ({raw_title} — considering)."
                )
                _update_livechart_tag(existing, "LiveChart Considering", media_tag)
                if existing["title"] not in demoted_secondary:
                    demoted_secondary.append(existing["title"])
            _apply_pinned_year(existing, existing["title"])
        else:
            reason = (
                "LiveChart Secondary backlog (considering — feature film/special)."
                if is_movie
                else "LiveChart Secondary backlog (considering)."
            )
            entry = {
                "title": title,
                "disabled": True,
                "watched": False,
                "category": 3,
                "mediaType": media_type,
                "serialization": "serialized",
                "categoryReason": reason,
                "moodTags": [media_tag, "LiveChart Considering"],
            }
            _apply_pinned_year(entry, title)
            shows.append(entry)
            by_key[key] = entry
            if is_movie:
                added_secondary_movies += 1
            else:
                added_secondary_series += 1

    # 5. Auto-disable shows dropped/removed from LiveChart active queues
    for s in shows:
        key = normalize_title_key(s["title"])
        if key in claimed_keys:
            continue
        tags = s.get("moodTags") or []
        if "LiveChart Now Watching" in tags or "LiveChart Primary" in tags:
            if not s.get("disabled") or s.get("category") == 4:
                s["disabled"] = True
                if s.get("category") == 4:
                    s["category"] = 3
                    s["serialization"] = "serialized"
                s["categoryReason"] = (
                    "Removed or dropped from LiveChart active queues — disabled automatically."
                )
                _update_livechart_tag(
                    s,
                    None,
                    "Anime Movie" if s.get("mediaType") == "anime_movie" else "Anime",
                )
                disabled_dropped.append(s["title"])

    save_source(data)
    stats: dict[str, Any] = {
        "promotedNowWatching": promoted_now_watching,
        "addedNowWatchingSeries": added_now_watching_series,
        "addedNowWatchingMovies": added_now_watching_movies,
        "promotedPrimary": promoted_primary,
        "addedPrimarySeries": added_primary_series,
        "addedPrimaryMovies": added_primary_movies,
        "graduatedCompleted": graduated_completed,
        "preservedCompleted": preserved_completed,
        "addedCompletedSeries": added_completed_series,
        "addedCompletedMovies": added_completed_movies,
        "demotedSecondary": demoted_secondary,
        "addedSecondarySeries": added_secondary_series,
        "addedSecondaryMovies": added_secondary_movies,
        "disabledDropped": disabled_dropped,
        "skippedDuplicates": skipped_duplicates,
        "totalInSource": len(shows),
    }
    print(
        f"LiveChart 4-tier import complete into {SOURCE_PATH}:\n"
        f"  - Now Watching (Cat 4, Enabled): +{added_now_watching_series} series, +{added_now_watching_movies} movies, "
        f"{len(promoted_now_watching)} promoted ({', '.join(promoted_now_watching) or 'none'})\n"
        f"  - Primary Queue (Cat 3, Enabled): +{added_primary_series} series, +{added_primary_movies} movies, "
        f"{len(promoted_primary)} promoted ({', '.join(promoted_primary) or 'none'})\n"
        f"  - Completed Library (Cat 1, Disabled for new/graduated): +{added_completed_series} series, "
        f"+{added_completed_movies} movies, {len(graduated_completed)} graduated, "
        f"{preserved_completed} existing Cat 1 preserved\n"
        f"  - Secondary Backlog (Cat 3, Disabled): +{added_secondary_series} series, +{added_secondary_movies} movies, "
        f"{len(demoted_secondary)} demoted\n"
        f"  - Auto-disabled dropped/removed LiveChart active items: {len(disabled_dropped)} "
        f"({', '.join(disabled_dropped) or 'none'})\n"
        f"  - Skipped duplicates/sequels collapsed onto base series: {skipped_duplicates}\n"
        f"  - Total entries now in {SOURCE_PATH}: {len(shows)}"
    )
    return stats


def main() -> None:
    parser = argparse.ArgumentParser(description="Manage RandomFlix source show list")
    sub = parser.add_subparsers(dest="cmd")

    sub.add_parser("list", help="List current shows in data/shows_source.json")
    sub.add_parser("summary", help="Summarize enriched shows in docs/data/catalog.json")

    add_p = sub.add_parser("add", help="Add or update a show in data/shows_source.json")
    add_p.add_argument("title", help="Show title")
    add_p.add_argument("--watched", action="store_true", help="Mark as already watched (Category 1)")
    add_p.add_argument("--category", type=int, choices=[1, 2, 3, 4], help="Explicit Category (1=Watched, 2=Background, 3=Active, 4=Now Watching)")
    add_p.add_argument("--vibe", help="1-sentence couch vibe")
    add_p.add_argument("--reason", help="Reason for category assignment")
    add_p.add_argument("--type", choices=["tv", "anime", "movie", "anime_movie", "collection"], help="Media type")
    add_p.add_argument("--disabled", action="store_true", help="Keep on list but disable from active database")
    add_p.add_argument("--enrich", action="store_true", help="Run catalog enrichment after adding")

    dis_p = sub.add_parser("disable", help="Disable a show (keep on list, exclude from active rotation)")
    dis_p.add_argument("title", help="Show title to disable")
    dis_p.add_argument("--enrich", action="store_true", help="Run catalog enrichment after disabling")

    en_p = sub.add_parser("enable", help="Re-enable a disabled show in active rotation")
    en_p.add_argument("title", help="Show title to enable")
    en_p.add_argument("--enrich", action="store_true", help="Run catalog enrichment after enabling")

    lc_p = sub.add_parser("import-livechart", help="Import four-tier LiveChart anime_watchlist.json into shows_source.json")
    lc_p.add_argument("--path", type=Path, default=DEFAULT_LIVECHART_PATH, help="Path to anime_watchlist.json")
    lc_p.add_argument("--enrich", action="store_true", help="Run catalog enrichment after importing")

    args = parser.parse_args()
    if args.cmd == "list":
        list_shows()
    elif args.cmd == "summary":
        summarize_catalog()
    elif args.cmd == "add":
        add_show(
            title=args.title,
            watched=args.watched,
            category=args.category,
            vibe=args.vibe,
            category_reason=args.reason,
            media_type=args.type,
            disabled=True if args.disabled else None,
        )
        if args.enrich:
            enrich_all()
    elif args.cmd == "disable":
        set_show_disabled(args.title, True)
        if args.enrich:
            enrich_all()
    elif args.cmd == "enable":
        set_show_disabled(args.title, False)
        if args.enrich:
            enrich_all()
    elif args.cmd == "import-livechart":
        import_livechart(args.path)
        if args.enrich:
            enrich_all()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
