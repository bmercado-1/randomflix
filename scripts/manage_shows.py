#!/usr/bin/env python3
"""
Helper CLI to list, add, or update shows in `data/shows_source.json`
and inspect `legacy/shows.csv`.
"""

from __future__ import annotations

import argparse
import json
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

LIVECHART_SEQUEL_TO_BASE: dict[str, str] = {
    "Mob Psycho 100": "Mob Psycho 100",
    "Blue Box": "Blue Box",
    "SAKAMOTO DAYS": "Sakamoto Days",
    "MASHLE: MAGIC AND MUSCLES": "Mashle: Magic and Muscles",
    "The Eminence in Shadow 2nd Season": "The Eminence in Shadow",
    "Kaguya-sama: Love Is War -Stairway to Adulthood-": "Kaguya-sama: Love Is War",
    "KONOSUBA -God's blessing on this wonderful world! 2": "KONOSUBA -God's blessing on this wonderful world!",
    "Clevatess II": "Clevatess",
    "Real Girl 2nd Season": "3D Kanojo: Real Girl",
    "My Happy Marriage Season 2": "My Happy Marriage",
    "My Happy Marriage Special Episodes": "My Happy Marriage",
    "Kamisama Kiss OVA": "Kamisama Kiss",
    "Is It Wrong to Try to Pick Up Girls in a Dungeon? II": "Is It Wrong to Try to Pick Up Girls in a Dungeon?",
    "Trapped in a Dating Sim: The World of Otome Games is Tough for Mobs Season 2": "Trapped in a Dating Sim: The World of Otome Games is Tough for Mobs",
    "Science Fell in Love, So I Tried to Prove It r=1-sinθ": "Science Fell in Love, So I Tried to Prove It",
    "Tsukimonogatari": "Bakemonogatari",
    "Demon Slayer: Kimetsu no Yaiba": "Demon Slayer: Kimetsu no Yaiba",
    "Food Wars! Shokugeki no Soma": "Food Wars! Shokugeki no Soma",
    "JUJUTSU KAISEN Season 2": "Jujutsu Kaisen",
    "Ascendance of a Bookworm OVA": "Ascendance of a Bookworm",
    "Nisekoi:": "Nisekoi",
    "Room Camp": "Laid-Back Camp",
}

LIVECHART_TITLE_NORMALIZATIONS: dict[str, str] = {
    "Cyberpunk: Edgerunners 2": "Cyberpunk: Edgerunners",
    "Shakugan no Shana: Season I": "Shakugan no Shana",
    "Momokuri (TV)": "Momokuri",
    "Kiss × Sis (TV)": "Kiss x Sis",
}


def import_livechart(watchlist_path: Path = DEFAULT_LIVECHART_PATH) -> None:
    if not watchlist_path.exists():
        raise FileNotFoundError(f"LiveChart watchlist not found: {watchlist_path}")

    wl = json.loads(watchlist_path.read_text(encoding="utf-8"))
    data = load_source()
    shows: list[dict[str, Any]] = data.setdefault("shows", [])
    by_key: dict[str, dict[str, Any]] = {
        normalize_title_key(s["title"]): s for s in shows
    }

    promoted_existing: list[str] = []
    added_primary_series = 0
    added_primary_movies = 0
    added_secondary_series = 0
    added_secondary_movies = 0
    skipped_duplicates = 0

    # 1. Process Primary (planning, paused, skipping) -> Category 3, Enabled
    for item in wl.get("primary", []):
        raw_title = (item.get("title") or "").strip()
        if not raw_title:
            continue
        status = item.get("status") or "planning"
        eps = item.get("total_episodes")
        is_movie = eps == 1

        if is_movie:
            title = raw_title
            key = normalize_title_key(title)
            if key in by_key:
                skipped_duplicates += 1
                continue
            entry: dict[str, Any] = {
                "title": title,
                "watched": False,
                "category": 3,
                "mediaType": "anime_movie",
                "serialization": "serialized",
                "categoryReason": f"LiveChart Primary queue ({status} — feature film/special).",
                "moodTags": ["Anime Movie", "LiveChart Primary"],
            }
            shows.append(entry)
            by_key[key] = entry
            added_primary_movies += 1
        else:
            mapped_title = LIVECHART_SEQUEL_TO_BASE.get(
                raw_title, LIVECHART_TITLE_NORMALIZATIONS.get(raw_title, raw_title)
            )
            key = normalize_title_key(mapped_title)
            if key in by_key:
                existing = by_key[key]
                existing["watched"] = False
                existing["category"] = 3
                existing.pop("disabled", None)
                existing["serialization"] = "serialized"
                existing["categoryReason"] = (
                    f"In LiveChart Primary queue ({raw_title} — {status}) — surfaced in Active Focus."
                )
                if existing["title"] not in promoted_existing:
                    promoted_existing.append(existing["title"])
            else:
                entry = {
                    "title": mapped_title,
                    "watched": False,
                    "category": 3,
                    "mediaType": "anime",
                    "serialization": "serialized",
                    "categoryReason": f"LiveChart Primary queue ({status}).",
                    "moodTags": ["Anime", "LiveChart Primary"],
                }
                shows.append(entry)
                by_key[key] = entry
                added_primary_series += 1

    # 2. Process Secondary (considering) -> Category 3, Disabled
    for item in wl.get("secondary", []):
        raw_title = (item.get("title") or "").strip()
        if not raw_title:
            continue
        eps = item.get("total_episodes")
        is_movie = eps == 1

        if is_movie:
            # Disambiguate 2010 Studio Deen movie from 2014 ufotable TV series
            title = (
                "Fate/stay night: Unlimited Blade Works (2010)"
                if raw_title == "Fate/stay night: Unlimited Blade Works"
                else raw_title
            )
            key = normalize_title_key(title)
            if key in by_key:
                skipped_duplicates += 1
                continue
            entry = {
                "title": title,
                "disabled": True,
                "watched": False,
                "category": 3,
                "mediaType": "anime_movie",
                "serialization": "serialized",
                "categoryReason": "LiveChart Secondary backlog (considering — feature film/special).",
                "moodTags": ["Anime Movie", "LiveChart Considering"],
            }
            if title.endswith("(2010)"):
                entry["year"] = 2010
            shows.append(entry)
            by_key[key] = entry
            added_secondary_movies += 1
        else:
            mapped_title = LIVECHART_SEQUEL_TO_BASE.get(
                raw_title, LIVECHART_TITLE_NORMALIZATIONS.get(raw_title, raw_title)
            )
            key = normalize_title_key(mapped_title)
            if key in by_key:
                skipped_duplicates += 1
                continue
            entry = {
                "title": mapped_title,
                "disabled": True,
                "watched": False,
                "category": 3,
                "mediaType": "anime",
                "serialization": "serialized",
                "categoryReason": "LiveChart Secondary backlog (considering).",
                "moodTags": ["Anime", "LiveChart Considering"],
            }
            shows.append(entry)
            by_key[key] = entry
            added_secondary_series += 1

    save_source(data)
    print(
        f"LiveChart import complete into {SOURCE_PATH}:\n"
        f"  - Promoted existing watched shows to Cat 3 (Active Focus, Enabled): {len(promoted_existing)}\n"
        f"  - Added Primary Anime Series (Cat 3, Enabled): {added_primary_series}\n"
        f"  - Added Primary Anime Movies (Cat 3, Enabled): {added_primary_movies}\n"
        f"  - Added Secondary Anime Series (Cat 3, Disabled): {added_secondary_series}\n"
        f"  - Added Secondary Anime Movies (Cat 3, Disabled): {added_secondary_movies}\n"
        f"  - Skipped duplicates/sequels already accounted for: {skipped_duplicates}\n"
        f"  - Total entries now in {SOURCE_PATH}: {len(shows)}"
    )


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

    lc_p = sub.add_parser("import-livechart", help="Import two-tier LiveChart anime_watchlist.json into shows_source.json")
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
