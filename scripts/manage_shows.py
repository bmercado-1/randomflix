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
        print(f"{i:2d}. {title:36s} | Cat {s['category']} | {mtype:5s} | {rt:2d}m | {seasons:2d}S/{eps:3d}E | {provs}")


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
        print(f"{i:2d}. {s['title']} [Cat {cat} | {watched}] — {s.get('vibe', '')}")


def add_show(
    title: str,
    watched: bool = False,
    category: int | None = None,
    vibe: str | None = None,
    category_reason: str | None = None,
    media_type: str | None = None,
    mood_tags: list[str] | None = None,
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

    if existing is None:
        shows.append(entry)
        print(f"Added '{title}' to {SOURCE_PATH}")
    else:
        print(f"Updated '{title}' in {SOURCE_PATH}")

    save_source(data)


def main() -> None:
    parser = argparse.ArgumentParser(description="Manage RandomFlix source show list")
    sub = parser.add_subparsers(dest="cmd")

    sub.add_parser("list", help="List current shows in data/shows_source.json")
    sub.add_parser("summary", help="Summarize enriched shows in docs/data/catalog.json")

    add_p = sub.add_parser("add", help="Add or update a show in data/shows_source.json")
    add_p.add_argument("title", help="Show title")
    add_p.add_argument("--watched", action="store_true", help="Mark as already watched (Category 1)")
    add_p.add_argument("--category", type=int, choices=[1, 2, 3], help="Explicit Category (1=Watched, 2=Background, 3=Active)")
    add_p.add_argument("--vibe", help="1-sentence couch vibe")
    add_p.add_argument("--reason", help="Reason for category assignment")
    add_p.add_argument("--type", choices=["tv", "anime", "collection"], help="Media type")
    add_p.add_argument("--enrich", action="store_true", help="Run catalog enrichment after adding")

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
        )
        if args.enrich:
            enrich_all()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
