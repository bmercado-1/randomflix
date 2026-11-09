#!/usr/bin/env python3
"""
RandomFlix 2.0 — Catalog Enrichment Pipeline

Reads the lean hand-picked show list from `data/shows_source.json`, enriches each
show with:
  1. Live US streaming availability & series-level deep links via JustWatch GraphQL API
  2. Android TV native `intent://` URLs (for launching native Google TV apps directly
     from TV Bro / BrowseHere on Hisense U8H Google TV)
  3. Poster artwork, release year, episode runtime, genres, and full episode list
     (for the opt-in "Roll Random Episode" button) via TVMaze / Jikan APIs
  4. Strict Category 1 / 2 / 3 classification & couch-vibe metadata

Outputs `docs/data/catalog.json` for the static Web App / PWA.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import time
import unicodedata
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parent.parent
SOURCE_PATH = ROOT_DIR / "data" / "shows_source.json"
CACHE_PATH = ROOT_DIR / "data" / "enrichment_cache.json"
LEGACY_CSV_PATH = ROOT_DIR / "legacy" / "shows.csv"
CATALOG_OUT_PATH = ROOT_DIR / "docs" / "data" / "catalog.json"

JUSTWATCH_GRAPHQL_URL = "https://apis.justwatch.com/graphql"
TVMAZE_SEARCH_URL = "https://api.tvmaze.com/singlesearch/shows"
JIKAN_SEARCH_URL = "https://api.jikan.moe/v4/anime"
ANILIST_GRAPHQL_URL = "https://graphql.anilist.co"

# Map of Android TV / Google TV native app package names for `intent://` deep links
ANDROID_TV_PACKAGES: dict[str, dict[str, str]] = {
    "netflix": {
        "name": "Netflix",
        "package": "com.netflix.ninja",
        "color": "#E50914",
    },
    "hulu": {
        "name": "Hulu",
        "package": "com.hulu.livingroomplus",
        "color": "#1CE783",
    },
    "max": {
        "name": "Max",
        "package": "com.wbd.stream",
        "color": "#002BE7",
    },
    "disney_plus": {
        "name": "Disney+",
        "package": "com.disney.disneyplus",
        "color": "#0063E5",
    },
    "prime_video": {
        "name": "Prime Video",
        "package": "com.amazon.amazonvideo.livingroom",
        "color": "#00A8E1",
    },
    "crunchyroll": {
        "name": "Crunchyroll",
        "package": "com.crunchyroll.crunchyroid",
        "color": "#F47521",
    },
    "peacock": {
        "name": "Peacock",
        "package": "com.peacocktv.peacockandroid",
        "color": "#000000",
    },
    "paramount_plus": {
        "name": "Paramount+",
        "package": "com.cbs.ott",
        "color": "#0064FF",
    },
    "apple_tv_plus": {
        "name": "Apple TV+",
        "package": "com.apple.atve.androidtv.appletv",
        "color": "#555555",
    },
    "pluto_tv": {
        "name": "Pluto TV",
        "package": "tv.pluto.android",
        "color": "#FFCC00",
    },
    "tubi": {
        "name": "Tubi",
        "package": "com.tubitv",
        "color": "#FA382F",
    },
    "hidive": {
        "name": "HIDIVE",
        "package": "com.hidive.android",
        "color": "#00AEEF",
    },
}

# Map JustWatch package shortNames / clearNames to our normalized provider key
# NOTE: Never fall back to URL-hostname guessing on JustWatch offers, because paid
# Amazon Channel add-ons (e.g. 'cra' = Crunchyroll Amazon Channel) use watch.amazon.com URLs.
JUSTWATCH_PROVIDER_MAP: dict[str, str] = {
    "nfx": "netflix",
    "nfk": "netflix",
    "nfa": "netflix",
    "hlu": "hulu",
    "mxx": "max",
    "hbm": "max",
    "dnp": "disney_plus",
    "amp": "prime_video",
    "prv": "prime_video",
    "cru": "crunchyroll",
    "pct": "peacock",
    "pcp": "peacock",
    "pmp": "paramount_plus",
    "atp": "apple_tv_plus",
    "ptv": "pluto_tv",
    "tbv": "tubi",
    "hdv": "hidive",
}


def normalize_title_key(title: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", title.lower())


def load_legacy_csv_lookup() -> dict[str, dict[str, Any]]:
    """Loads legacy/shows.csv so we can use old URLs/categories as reference or fallback."""
    lookup: dict[str, dict[str, Any]] = {}
    if not LEGACY_CSV_PATH.exists():
        return lookup

    with LEGACY_CSV_PATH.open("r", encoding="utf-8", errors="ignore") as f:
        reader = csv.DictReader(f)
        for row in reader:
            name = (row.get("Name") or "").strip()
            url = (row.get("Show-URL") or "").strip()
            cat_str = (row.get("Category") or "").strip()
            if not name or name.startswith("#"):
                continue
            if url and not url.startswith("http"):
                url = "https://" + url
            # Modernize legacy hbomax.com links to play.max.com
            url = url.replace("play.hbomax.com", "play.max.com")
            cat = int(cat_str) if cat_str.isdigit() else 2
            entry = {
                "title": name,
                "legacyUrl": url,
                "legacyCategory": cat,
                "legacyService": infer_provider_from_url(url),
            }
            norm = normalize_title_key(name)
            lookup[norm] = entry

    # Map common canonical title aliases to legacy keys
    alias_map = {
        "csicrimesceneinvestigation": "csi",
        "laworderspecialvictimsunit": "lawandordersvu",
        "starwarstheclonewars": "starwarsclonewars",
        "pokmonindigoleague": "pokemontheindigoleague",
    }
    for canonical_key, legacy_key in alias_map.items():
        if legacy_key in lookup and canonical_key not in lookup:
            lookup[canonical_key] = lookup[legacy_key]

    return lookup


# Series-level hub overrides for providers where JustWatch returns an episode `/watch/` link.
# Every Hulu URL below was verified via live HTTP redirect from Hulu; every Crunchyroll URL
# was verified via live browser redirect on crunchyroll.com.
SERIES_HUB_OVERRIDES: dict[tuple[str, str], str] = {
    ("americandad", "hulu"): "https://www.hulu.com/series/american-dad-977c8e25-cde0-41b7-80ce-e746f2d2093f",
    ("brooklynninenine", "hulu"): "https://www.hulu.com/series/brooklyn-nine-nine-daf48b7a-6cd7-4ef6-b639-a4811ec95232",
    ("community", "hulu"): "https://www.hulu.com/series/community-200c56d4-124c-41a1-b7d2-688f86f432bf",
    ("familyguy", "hulu"): "https://www.hulu.com/series/family-guy-3c3c0f8b-7366-4d15-88ab-18050285978e",
    ("futurama", "hulu"): "https://www.hulu.com/series/futurama-85bf4cc1-cd8b-4469-ad87-7289217a0b74",
    ("howimetyourmother", "hulu"): "https://www.hulu.com/series/how-i-met-your-mother-bc68ac79-3ace-4427-9ec0-5ee6f314d194",
    ("scrubs", "hulu"): "https://www.hulu.com/series/scrubs-2001-bba197b5-eb03-4a09-b5f6-f04c053471d7",
    ("thegoodplace", "hulu"): "https://www.hulu.com/series/the-good-place-f11df77f-115e-4eba-8efa-264f0ff322d0",
    ("thesimpsons", "hulu"): "https://www.hulu.com/series/the-simpsons-c88bb35c-880b-437e-9187-ab59b52df1a2",
    ("bones", "hulu"): "https://www.hulu.com/series/bones-08cc467f-2057-4331-825a-1f993c79c862",
    ("csicrimesceneinvestigation", "hulu"): "https://www.hulu.com/series/csi-crime-scene-investigation-e316aa0d-6df1-445b-98d9-ea1d165bcf81",
    ("house", "hulu"): "https://www.hulu.com/series/house-ef39603f-eb90-4248-8237-f6168d7c1be1",
    ("laworderspecialvictimsunit", "hulu"): "https://www.hulu.com/series/law-order-special-victims-unit-720ef5c1-fc77-4924-98c5-491455a06895",
    ("lietome", "hulu"): "https://www.hulu.com/series/lie-to-me-3ff40a52-bb7f-4c21-9f9d-19e50368778e",
    ("bleach", "hulu"): "https://www.hulu.com/series/bleach-0c265948-3450-40ad-89b4-883af457f36d",
    ("fatestaynight", "hulu"): "https://www.hulu.com/series/fate-stay-night-c0277bb9-6026-449c-8cb2-4ee7f298e715",
    ("fullmetalalchemistbrotherhood", "hulu"): "https://www.hulu.com/series/fullmetal-alchemist-brotherhood-213ddd1e-0c45-4f84-bb25-ea90ffd6507c",
    ("naruto", "hulu"): "https://www.hulu.com/series/naruto-993d48dc-d507-47cb-8cca-23e6794f6f66",
    ("narutoshippuden", "hulu"): "https://www.hulu.com/series/naruto-shippuden-c6321cb1-1879-4d7f-9e2f-8d7d4fc55544",
    ("persona5theanimation", "hulu"): "https://www.hulu.com/series/persona5-the-animation-6507e2ba-9faf-49e9-978f-6718a365c4fd",
    ("frierenbeyondjourneysend", "hulu"): "https://www.hulu.com/series/frieren-beyond-journeys-end-1d4725f8-06d1-43fb-a077-72143ac5502f",
    ("mashlemagicandmuscles", "hulu"): "https://www.hulu.com/series/mashle-magic-and-muscles-588f6e4a-42f1-48dd-931a-605ae4eec3e4",
    ("theapothecarydiaries", "hulu"): "https://www.hulu.com/series/the-apothecary-diaries-d7b5390e-b8cb-4cc3-ba7c-7ed570355d7d",
    ("rascaldoesnotdreamofbunnygirlsenpai", "hulu"): "https://www.hulu.com/series/rascal-does-not-dream-of-bunny-girl-senpai-e4c45f43-dc4b-44ce-a9b8-14139ac1af69",
    ("misskobayashisdragonmaid", "hulu"): "https://www.hulu.com/series/miss-kobayashis-dragon-maid-8649fd36-8025-412a-bec7-2e03fde2ea77",
    ("thedangersinmyheart", "hulu"): "https://www.hulu.com/series/the-dangers-in-my-heart-3b5bdff1-01cb-499d-a250-9158240a9e2b",
    ("insomniacsafterschool", "hulu"): "https://www.hulu.com/series/insomniacs-after-school-a625260a-4472-4239-9400-9083a88033eb",
    ("witchwatch", "hulu"): "https://www.hulu.com/series/witch-watch-7f008578-f8b2-4c27-8e5b-64320349ce63",
    ("mushokutenseijoblessreincarnation", "hulu"): "https://www.hulu.com/series/mushoku-tensei-jobless-reincarnation-787a5fb4-9cba-4a69-96b2-4fb3b10c860a",
    ("campfirecookinginanotherworldwithmyabsurdskill", "hulu"): "https://www.hulu.com/series/campfire-cooking-in-another-world-with-my-absurd-skill-fc20b0bc-90b6-45b3-b56a-ad3a5cb2b855",
    ("farminglifeinanotherworld", "hulu"): "https://www.hulu.com/series/farming-life-in-another-world-40489af2-d45a-40e0-8607-e3deac505971",
    ("isitwrongtotrytopickupgirlsinadungeon", "hulu"): "https://www.hulu.com/series/is-it-wrong-to-try-to-pick-up-girls-in-a-dungeon-fc1b26af-bd07-4034-95e6-a494d8528069",
    ("theeminenceinshadow", "hulu"): "https://www.hulu.com/series/the-eminence-in-shadow-66f37cf4-dba5-4511-ae26-e4092df1668b",
    ("thoughiamanineptvillainess", "hulu"): "https://www.hulu.com/series/though-i-am-an-inept-villainess-8a91ef01-78f6-4c33-9566-841da5a9b053",
    ("codegeasslelouchoftherebellion", "crunchyroll"): "https://www.crunchyroll.com/series/GY2P9ED0Y/code-geass",
    ("fullmetalalchemistbrotherhood", "crunchyroll"): "https://www.crunchyroll.com/series/GRGGPG93R/fullmetal-alchemist-brotherhood",
    ("hellsing", "crunchyroll"): "https://www.crunchyroll.com/series/G649DPXQY/hellsing",
    ("hellsingultimate", "crunchyroll"): "https://www.crunchyroll.com/series/GYWEQ4Q3Y/hellsing-ultimate",
    ("naruto", "crunchyroll"): "https://www.crunchyroll.com/series/GY9PJ5KWR/naruto",
    ("narutoshippuden", "crunchyroll"): "https://www.crunchyroll.com/series/GYQ4MW246/naruto-shippuden",
    ("ouranhighschoolhostclub", "crunchyroll"): "https://www.crunchyroll.com/series/GRGGJWD2R/ouran-high-school-host-club",
    ("persona5theanimation", "crunchyroll"): "https://www.crunchyroll.com/series/G6VDWKM76/persona5-the-animation",
    ("horimiya", "crunchyroll"): "https://www.crunchyroll.com/series/G9VHN9P43/horimiya",
    ("misskobayashisdragonmaid", "crunchyroll"): "https://www.crunchyroll.com/series/G6497Z43Y/miss-kobayashis-dragon-maid",
    ("thequintessentialquintuplets", "crunchyroll"): "https://www.crunchyroll.com/series/GY4PD7Z06/the-quintessential-quintuplets",
    ("theiceguyandhiscoolfemalecolleague", "crunchyroll"): "https://www.crunchyroll.com/series/GW4HM75NP/the-ice-guy-and-his-cool-female-colleague",
    ("lycorisrecoil", "crunchyroll"): "https://www.crunchyroll.com/series/G1XHJV2X9/lycoris-recoil",
    ("kaguyasamaloveiswar", "crunchyroll"): "https://www.crunchyroll.com/series/GRJ0J828Y/kaguya-sama-love-is-war",
    ("aharensanisindecipherable", "crunchyroll"): "https://www.crunchyroll.com/series/GNVHKN72N/aharen-san-wa-hakarenai",
    ("recoveryofanmmojunkie", "crunchyroll"): "https://www.crunchyroll.com/series/GR49WNQE6/recovery-of-an-mmo-junkie",
    ("banishedfromtheherospartyidecidedtoliveaquietlifeinthecountryside", "crunchyroll"): "https://www.crunchyroll.com/series/G9VHN974E/banished-from-the-heros-party-i-decided-to-live-a-quiet-life-in-the-countryside",
    ("fruitsbasket2019", "crunchyroll"): "https://www.crunchyroll.com/series/G6ZJMGEXY/fruits-basket-2019",
    ("thedukeofdeathandhismaid", "crunchyroll"): "https://www.crunchyroll.com/series/G79H23V0G/the-duke-of-death-and-his-maid",
    ("hyouka", "crunchyroll"): "https://www.crunchyroll.com/series/G6P8G7V86/hyouka",
    ("mushokutenseijoblessreincarnation", "crunchyroll"): "https://www.crunchyroll.com/series/G24H1N3MP/mushoku-tensei-jobless-reincarnation",
    ("konosubagodsblessingonthiswonderfulworld", "crunchyroll"): "https://www.crunchyroll.com/series/GYE5K3GQR/konosuba---gods-blessing-on-this-wonderful-world",
    ("thesaintsmagicpowerisomnipotent", "crunchyroll"): "https://www.crunchyroll.com/series/G1XHJV3P3/the-saints-magic-power-is-omnipotent",
    ("teasingmastertakagisan", "hidive"): "https://www.hidive.com/tv/teasing-master-takagi-san",
}

# Live-verified Crunchyroll episode URLs for Fullmetal Alchemist: Brotherhood
# (JustWatch still indexes legacy Funimation GE0000* IDs for FMAB episodes)
CRUNCHYROLL_EPISODE_OVERRIDES: dict[str, dict[int, str]] = {
    "fullmetalalchemistbrotherhood": {
        1: "https://www.crunchyroll.com/watch/GYQ4M4216/fullmetal-alchemist",
        2: "https://www.crunchyroll.com/watch/GRWEXEPGR/the-first-day",
        3: "https://www.crunchyroll.com/watch/G609Q9896/city-of-heresy",
        4: "https://www.crunchyroll.com/watch/G6752581R/an-alchemists-anguish",
        5: "https://www.crunchyroll.com/watch/GYX040Z3R/rain-of-sorrows",
        6: "https://www.crunchyroll.com/watch/GR19598V6/road-of-hope",
        7: "https://www.crunchyroll.com/watch/GYNQ1QE3Y/hidden-truths",
        8: "https://www.crunchyroll.com/watch/G6MG1G026/the-fifth-laboratory",
        9: "https://www.crunchyroll.com/watch/G63VGV8XY/created-feelings",
        10: "https://www.crunchyroll.com/watch/GR2PWPZ7R/separate-destinations",
        11: "https://www.crunchyroll.com/watch/GRZXQXPVY/miracle-at-rush-valley",
        12: "https://www.crunchyroll.com/watch/G6Q4M4X1R/one-is-all-all-is-one",
        13: "https://www.crunchyroll.com/watch/GYWEXE8GY/beasts-of-dublith",
        14: "https://www.crunchyroll.com/watch/GR09Q9E9R/those-who-lurk-underground",
        15: "https://www.crunchyroll.com/watch/GR7525N1Y/envoy-from-the-east",
        16: "https://www.crunchyroll.com/watch/G6X04083Y/footsteps-of-a-comrade-in-arms",
        17: "https://www.crunchyroll.com/watch/GY19597VR/cold-flame",
        18: "https://www.crunchyroll.com/watch/G6NQ1QZ36/the-arrogant-palm-of-a-small-human",
        19: "https://www.crunchyroll.com/watch/GRMG1GZ2R/death-of-the-undying",
        20: "https://www.crunchyroll.com/watch/GR3VGVXX6/father-before-the-grave",
        21: "https://www.crunchyroll.com/watch/GY2PWP97Y/advance-of-the-fool",
        22: "https://www.crunchyroll.com/watch/GYZXQXZV6/backs-in-the-distance",
        23: "https://www.crunchyroll.com/watch/GRQ4M4Z1Y/girl-on-the-battlefield",
        24: "https://www.crunchyroll.com/watch/G6WEXE9G6/inside-the-belly",
        25: "https://www.crunchyroll.com/watch/GY09Q9Z9Y/doorway-of-darkness",
        26: "https://www.crunchyroll.com/watch/GY7525D16/reunion",
        27: "https://www.crunchyroll.com/watch/GRX040D36/interlude-party",
        28: "https://www.crunchyroll.com/watch/G61959PVY/father",
        29: "https://www.crunchyroll.com/watch/GRNQ1QK3R/struggle-of-the-fool",
        30: "https://www.crunchyroll.com/watch/GYMG1GN2Y/the-ishvalan-war-of-extermination",
        31: "https://www.crunchyroll.com/watch/GY3VGV5XR/the-520-cens-promise",
        32: "https://www.crunchyroll.com/watch/G62PWPQ76/the-fuhrers-son",
        33: "https://www.crunchyroll.com/watch/G6ZXQX1VR/the-northern-wall-of-briggs",
        34: "https://www.crunchyroll.com/watch/GYQ4M4516/ice-queen",
        35: "https://www.crunchyroll.com/watch/GRWEXEJGR/the-shape-of-this-country",
        36: "https://www.crunchyroll.com/watch/G609Q9096/family-portrait",
        37: "https://www.crunchyroll.com/watch/G67525J1R/the-first-homunculus",
        38: "https://www.crunchyroll.com/watch/GYX040N3R/conflict-at-baschool",
        39: "https://www.crunchyroll.com/watch/GR1959EV6/daydream",
        40: "https://www.crunchyroll.com/watch/GYNQ1QW3Y/homunculus-the-dwarf-in-the-flask",
        41: "https://www.crunchyroll.com/watch/G6MG1G526/the-abyss",
        42: "https://www.crunchyroll.com/watch/G63VGV9XY/signs-of-a-counter-offensive",
        43: "https://www.crunchyroll.com/watch/GR2PWP77R/bite-of-the-ant",
        44: "https://www.crunchyroll.com/watch/GRZXQXMVY/revving-at-full-throttle",
        45: "https://www.crunchyroll.com/watch/G6Q4M4E1R/the-promised-day",
        46: "https://www.crunchyroll.com/watch/GYWEXE5GY/looming-shadows",
        47: "https://www.crunchyroll.com/watch/GR09Q9K9R/emissary-of-darkness",
        48: "https://www.crunchyroll.com/watch/GR7525G1Y/the-oath-in-the-tunnel",
        49: "https://www.crunchyroll.com/watch/G6X040W3Y/filial-affection",
        50: "https://www.crunchyroll.com/watch/GY1959DVR/upheaval-in-central",
        51: "https://www.crunchyroll.com/watch/GYQ4M4N36/the-immortal-legion",
        52: "https://www.crunchyroll.com/watch/GRWEXE5QR/combined-strength",
        53: "https://www.crunchyroll.com/watch/G609Q9KE6/flame-of-vengeance",
        54: "https://www.crunchyroll.com/watch/G67525GJR/beyond-the-inferno",
        55: "https://www.crunchyroll.com/watch/GYX040WKR/the-adults-way-of-life",
        56: "https://www.crunchyroll.com/watch/GR1959D26/the-return-of-the-fuhrer",
        57: "https://www.crunchyroll.com/watch/GYNQ1QG0Y/eternal-leave",
        58: "https://www.crunchyroll.com/watch/G6MG1GWG6/sacrifices",
        59: "https://www.crunchyroll.com/watch/G63VGVNWY/lost-light",
        60: "https://www.crunchyroll.com/watch/GR2PWPJER/eye-of-heaven-gateway-of-earth",
        61: "https://www.crunchyroll.com/watch/GRZXQXV9Y/he-who-would-swallow-god",
        62: "https://www.crunchyroll.com/watch/G6Q4M473R/a-fierce-counterattack",
        63: "https://www.crunchyroll.com/watch/GYWEXENQY/the-other-side-of-the-gateway",
        64: "https://www.crunchyroll.com/watch/GR09Q94ER/journeys-end",
    }
}


def strip_diacritics(text: str) -> str:
    return unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")


def strip_year_suffix(title: str) -> str:
    return re.sub(r"\s*\(\d{4}\)\s*$", "", title).strip()


def slugify_title(title: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", strip_diacritics(title).lower()).strip("-")


def titles_match(cand_title: str, ref_titles: list[str]) -> bool:
    """Checks if a candidate title from JustWatch/TVMaze reasonably matches any reference title."""
    cand_ascii = strip_diacritics(strip_year_suffix(cand_title))
    cand_norm = normalize_title_key(cand_ascii)
    if not cand_norm:
        return False
    cand_prefix = normalize_title_key(re.split(r"[:~]", cand_ascii, maxsplit=1)[0])
    cand_tokens = {
        t
        for t in re.findall(r"[a-z0-9]+", cand_ascii.lower())
        if len(t) > 2 and t not in {"the", "and", "for", "with", "from", "into"}
    }
    for ref in ref_titles:
        if not ref:
            continue
        ref_ascii = strip_diacritics(strip_year_suffix(ref))
        ref_norm = normalize_title_key(ref_ascii)
        if not ref_norm:
            continue
        if cand_norm == ref_norm:
            return True
        ref_prefix = normalize_title_key(re.split(r"[:~]", ref_ascii, maxsplit=1)[0])
        if len(cand_prefix) >= 10 and cand_prefix == ref_prefix:
            return True
        shorter, longer = (
            (cand_norm, ref_norm) if len(cand_norm) <= len(ref_norm) else (ref_norm, cand_norm)
        )
        if len(shorter) >= 6 and shorter in longer:
            return True
        ref_tokens = {
            t
            for t in re.findall(r"[a-z0-9]+", ref_ascii.lower())
            if len(t) > 2 and t not in {"the", "and", "for", "with", "from", "into"}
        }
        if cand_tokens and ref_tokens:
            overlap = len(cand_tokens & ref_tokens) / min(len(cand_tokens), len(ref_tokens))
            if overlap >= 0.65 and min(len(cand_tokens), len(ref_tokens)) >= 2:
                return True
    return False


def unwrap_affiliate_url(web_url: str) -> str:
    """Unwraps affiliate redirect wrappers (e.g. crunchyroll.pxf.io?u=...)."""
    if "pxf.io" in web_url and "u=" in web_url:
        parsed = urllib.parse.urlparse(web_url)
        qs = urllib.parse.parse_qs(parsed.query)
        if "u" in qs and qs["u"]:
            return qs["u"][0]
    return web_url


def resolve_hulu_series_url(watch_url: str) -> str | None:
    """Follows HTTP redirect on a Hulu /watch/<uuid> link to get the canonical /series/<slug>-<uuid> hub URL."""
    try:
        req = urllib.request.Request(
            watch_url,
            headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
                "Accept": "text/html,application/xhtml+xml",
            },
        )
        with urllib.request.urlopen(req, timeout=8) as resp:
            final_url = resp.geturl()
            if "/series/" in final_url:
                return final_url.split("?")[0]
    except Exception as exc:
        print(f"  [Hulu Redirect] Warning resolving '{watch_url}': {exc}")
    return None


_CR_ACCESS_TOKEN: str | None = None


def get_crunchyroll_anonymous_token() -> str | None:
    """Acquires an anonymous Crunchyroll web client bearer token to resolve /watch/<ep_id> to /series/<id>."""
    global _CR_ACCESS_TOKEN
    if _CR_ACCESS_TOKEN:
        return _CR_ACCESS_TOKEN
    for basic in (
        "bm9haWhkZXZtXzZpeWcwYThsMHE6",
        "a3ZvcGlzdXZ6Yy0teG96Y21kMXk6R21JSTExenVPVnRnTjdlSWZrSlpibzVuLTRHTlZ0cU8=",
    ):
        try:
            req = urllib.request.Request(
                "https://www.crunchyroll.com/auth/v1/token",
                data=b"grant_type=client_id",
                headers={
                    "Authorization": f"Basic {basic}",
                    "Content-Type": "application/x-www-form-urlencoded",
                    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
                },
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=8) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                if data.get("access_token"):
                    _CR_ACCESS_TOKEN = data["access_token"]
                    return _CR_ACCESS_TOKEN
        except Exception:
            continue
    return None


def resolve_crunchyroll_series_url(
    watch_or_legacy_url: str,
    anilist_ep_offers: dict[str, str] | None = None,
) -> str | None:
    """Resolves a Crunchyroll /watch/<ep_id> or legacy slug URL to its canonical /series/<id>/<slug> hub."""
    candidate_ep_ids: list[str] = []
    m_watch = re.search(r"crunchyroll\.com/watch/([A-Z0-9]+)", watch_or_legacy_url)
    if m_watch and not m_watch.group(1).startswith("GE000"):
        candidate_ep_ids.append(m_watch.group(1))
    if anilist_ep_offers:
        for ep_url in anilist_ep_offers.values():
            m_ep = re.search(r"crunchyroll\.com/watch/([A-Z0-9]+)", ep_url)
            if m_ep and m_ep.group(1) not in candidate_ep_ids:
                candidate_ep_ids.append(m_ep.group(1))
                break

    if not candidate_ep_ids:
        return None

    token = get_crunchyroll_anonymous_token()
    if not token:
        return None

    for ep_id in candidate_ep_ids:
        try:
            req = urllib.request.Request(
                f"https://www.crunchyroll.com/content/v2/cms/objects/{ep_id}?locale=en-US",
                headers={
                    "Authorization": f"Bearer {token}",
                    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
                },
            )
            with urllib.request.urlopen(req, timeout=8) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                items = data.get("data") or []
                if items:
                    ep_meta = items[0].get("episode_metadata") or {}
                    series_id = ep_meta.get("series_id")
                    slug = ep_meta.get("series_slug_title")
                    if series_id:
                        return (
                            f"https://www.crunchyroll.com/series/{series_id}/{slug}"
                            if slug
                            else f"https://www.crunchyroll.com/series/{series_id}"
                        )
        except Exception:
            continue
    return None


def normalize_crunchyroll_url(url: str) -> str:
    url = url.strip()
    url = re.sub(r"^https?://(?:beta\.|www\.)?crunchyroll\.com/", "https://www.crunchyroll.com/", url)
    return url


def sanitize_series_url(
    web_url: str,
    prov_key: str,
    norm_key: str,
    title: str,
    legacy_info: dict[str, Any],
    anilist_providers: dict[str, str] | None = None,
    anilist_ep_offers: dict[str, str] | None = None,
) -> str | None:
    """
    Ensures every provider deep link opens the SERIES hub page (where 'Continue Watching'
    or 'Next Episode' lives) and NEVER a Season 1 Episode 1 playback URL that would
    restart the user's progress.
    """
    if not web_url:
        return None

    # 1. Check explicit verified series-hub overrides first
    if (norm_key, prov_key) in SERIES_HUB_OVERRIDES:
        return SERIES_HUB_OVERRIDES[(norm_key, prov_key)]

    # 2. Unwrap affiliate redirect wrappers (e.g. crunchyroll.pxf.io?u=...)
    web_url = unwrap_affiliate_url(web_url)
    if "crunchyroll.com" in web_url:
        web_url = normalize_crunchyroll_url(web_url)

    # 3. Provider-specific episode-suffix stripping & live redirect resolution
    if prov_key == "netflix":
        if "/watch/" in web_url and anilist_providers and "/title/" in (anilist_providers.get("netflix") or ""):
            web_url = anilist_providers["netflix"]
        m_jbv = re.search(r"jbv=(\d+)", web_url)
        if m_jbv:
            return f"https://www.netflix.com/title/{m_jbv.group(1)}"
        m_title = re.search(r"netflix\.com/(?:[a-zA-Z-]+/)?(?:title|watch)/(\d+)", web_url)
        if m_title:
            return f"https://www.netflix.com/title/{m_title.group(1)}"
        return web_url

    if prov_key == "hidive":
        if "/interstitial/" in web_url:
            if anilist_providers and "/tv/" in (anilist_providers.get("hidive") or ""):
                return anilist_providers["hidive"]
            return f"https://www.hidive.com/tv/{slugify_title(strip_year_suffix(title))}"
        return web_url

    if prov_key == "peacock":
        # Strip /seasons/1/episodes/... from Peacock asset URLs
        web_url = re.sub(r"/seasons/\d+/episodes/.*$", "", web_url)
        return web_url

    if prov_key == "paramount_plus":
        # Strip /video/... and query params from Paramount+ show URLs
        web_url = re.sub(r"/video/.*$", "/", web_url.split("?")[0])
        return web_url

    if prov_key == "pluto_tv":
        # Strip /season/... and query params from Pluto TV series URLs
        web_url = re.sub(r"/season/.*$", "", web_url.split("?")[0])
        return web_url

    if prov_key == "hulu":
        if "/watch/" in web_url:
            resolved = resolve_hulu_series_url(web_url)
            if resolved:
                return resolved
            if anilist_providers and "/series/" in (anilist_providers.get("hulu") or ""):
                return anilist_providers["hulu"]
            if (
                legacy_info.get("legacyService") == "hulu"
                and legacy_info.get("legacyUrl")
                and "/series/" in legacy_info["legacyUrl"]
            ):
                return legacy_info["legacyUrl"]
            return None
        return web_url

    if prov_key == "crunchyroll":
        if "/series/" not in web_url:
            if anilist_providers and anilist_providers.get("crunchyroll"):
                al_cr = normalize_crunchyroll_url(anilist_providers["crunchyroll"])
                if "/series/" in al_cr:
                    return al_cr
            if (
                legacy_info.get("legacyService") == "crunchyroll"
                and legacy_info.get("legacyUrl")
                and "/series/" in legacy_info["legacyUrl"]
            ):
                return legacy_info["legacyUrl"]
            resolved_cr = resolve_crunchyroll_series_url(web_url, anilist_ep_offers=anilist_ep_offers)
            if resolved_cr:
                return resolved_cr
            return None if "/watch/" in web_url else web_url
        return web_url

    if prov_key == "tubi":
        # Guard against Pokémon: Indigo League matching Pokémon XY on Tubi
        if norm_key == "pokmonindigoleague" and "xy" in web_url.lower():
            return None
        return web_url

    return web_url


def normalize_providers_list(
    raw_providers: list[dict[str, Any]],
    norm_key: str,
    title: str,
    legacy_info: dict[str, Any],
    item: dict[str, Any],
    anilist_providers: dict[str, str] | None = None,
    anilist_ep_offers: dict[str, str] | None = None,
) -> list[dict[str, Any]]:
    """Sanitizes all provider URLs to series-level hubs and rebuilds Android TV intent URLs."""
    cleaned: list[dict[str, Any]] = []
    seen_ids: set[str] = set()

    # Use JustWatch US as the authoritative source of US streaming availability;
    # fall back to AniList anime specialty streaming links (Crunchyroll/HIDIVE) only when JustWatch US has no providers yet.
    combined_candidates = list(raw_providers)
    if not combined_candidates and anilist_providers:
        for prov_key, al_url in anilist_providers.items():
            if prov_key not in ("crunchyroll", "hidive"):
                continue
            if any(non_us in al_url for non_us in (".co.uk", "/-/fr/", "/region/", "/id-en/", "/to/title/")):
                continue
            if prov_key in ANDROID_TV_PACKAGES and al_url:
                pkg_meta = ANDROID_TV_PACKAGES[prov_key]
                combined_candidates.append(
                    {
                        "id": prov_key,
                        "name": pkg_meta["name"],
                        "color": pkg_meta["color"],
                        "monetization": "flatrate",
                        "webUrl": al_url,
                    }
                )

    for p in combined_candidates:
        prov_key = p.get("id") or ""
        raw_url = p.get("webUrl") or ""
        series_url = sanitize_series_url(
            raw_url,
            prov_key,
            norm_key,
            title,
            legacy_info,
            anilist_providers=anilist_providers,
            anilist_ep_offers=anilist_ep_offers,
        )
        if not series_url or prov_key in seen_ids:
            continue
        seen_ids.add(prov_key)
        pkg_meta = ANDROID_TV_PACKAGES.get(prov_key, {})
        cleaned.append(
            {
                "id": prov_key,
                "name": pkg_meta.get("name", p.get("name") or prov_key.title()),
                "color": pkg_meta.get("color", p.get("color") or "#4A5568"),
                "monetization": p.get("monetization") or "flatrate",
                "webUrl": series_url,
                "androidTvIntentUrl": build_android_tv_intent(series_url, prov_key),
            }
        )

    if not cleaned:
        fallback_url = item.get("fallbackUrl") or legacy_info.get("legacyUrl") or ""
        fallback_prov = item.get("fallbackService") or infer_provider_from_url(fallback_url)
        if fallback_url and fallback_prov:
            pkg_meta = ANDROID_TV_PACKAGES.get(fallback_prov, {})
            seen_ids.add(fallback_prov)
            cleaned.append(
                {
                    "id": fallback_prov,
                    "name": pkg_meta.get("name", fallback_prov.replace("_", " ").title()),
                    "color": pkg_meta.get("color", "#4A5568"),
                    "monetization": "flatrate",
                    "webUrl": fallback_url,
                    "androidTvIntentUrl": build_android_tv_intent(fallback_url, fallback_prov),
                }
            )

    # Hulu on Disney+ integration: US Hulu series share the exact same 36-char
    # BAMTech/Disney entity UUID (`https://www.disneyplus.com/browse/entity-<uuid>`),
    # even when JustWatch only tags the standalone `hlu` package.
    if "hulu" in seen_ids and "disney_plus" not in seen_ids:
        hulu_entry = next((c for c in cleaned if c["id"] == "hulu"), None)
        if hulu_entry:
            m = re.search(
                r"([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})",
                hulu_entry["webUrl"],
            )
            if m:
                entity_uuid = m.group(1).lower()
                dnp_url = f"https://www.disneyplus.com/browse/entity-{entity_uuid}"
                dnp_meta = ANDROID_TV_PACKAGES["disney_plus"]
                seen_ids.add("disney_plus")
                cleaned.append(
                    {
                        "id": "disney_plus",
                        "name": dnp_meta["name"],
                        "color": dnp_meta["color"],
                        "monetization": hulu_entry.get("monetization") or "flatrate",
                        "webUrl": dnp_url,
                        "androidTvIntentUrl": build_android_tv_intent(dnp_url, "disney_plus"),
                    }
                )

    return cleaned


def infer_provider_from_url(url: str) -> str | None:
    u = url.lower()
    if "netflix.com" in u:
        return "netflix"
    if "hulu.com" in u:
        return "hulu"
    if "hbomax.com" in u or "max.com" in u:
        return "max"
    if "disneyplus.com" in u or "disney.com" in u:
        return "disney_plus"
    if "amazon.com" in u or "primevideo.com" in u:
        return "prime_video"
    if "crunchyroll.com" in u:
        return "crunchyroll"
    if "pluto.tv" in u:
        return "pluto_tv"
    if "peacocktv.com" in u:
        return "peacock"
    if "paramountplus.com" in u:
        return "paramount_plus"
    if "tubitv.com" in u:
        return "tubi"
    return None


def build_android_tv_intent(web_url: str, provider_key: str) -> str:
    """
    Constructs an Android `intent://` URI that forces Android TV browsers
    (TV Bro / BrowseHere on Hisense U8H Google TV) to hand off directly to
    the native TV streaming app instead of opening the desktop web player.
    """
    if not web_url:
        return ""
    pkg_info = ANDROID_TV_PACKAGES.get(provider_key)
    if not pkg_info:
        return web_url

    parsed = urllib.parse.urlparse(web_url)
    scheme = parsed.scheme or "https"
    host_and_path = web_url[len(f"{scheme}://") :] if web_url.startswith(f"{scheme}://") else web_url
    fallback_encoded = urllib.parse.quote(web_url, safe="")
    package = pkg_info["package"]

    # Netflix Android TV (com.netflix.ninja) ignores deep-link URIs and lands on the
    # home screen unless the Intent includes the String extra `S.source=30`.
    if provider_key == "netflix":
        sep = "&" if "?" in host_and_path else "?"
        if "source=" not in host_and_path:
            host_and_path = f"{host_and_path}{sep}source=30"
        return (
            f"intent://{host_and_path}#Intent;"
            f"scheme={scheme};"
            f"package={package};"
            f"action=android.intent.action.VIEW;"
            f"S.source=30;"
            f"S.browser_fallback_url={fallback_encoded};"
            f"end"
        )

    return (
        f"intent://{host_and_path}#Intent;"
        f"scheme={scheme};"
        f"package={package};"
        f"action=android.intent.action.VIEW;"
        f"S.browser_fallback_url={fallback_encoded};"
        f"end"
    )


def query_justwatch_us(
    title: str,
    target_year: int | None = None,
    alt_titles: list[str] | None = None,
    expected_year: int | None = None,
) -> dict[str, Any] | None:
    """
    Queries JustWatch public GraphQL API for US streaming offers (FLATRATE/FREE/ADS)
    and series-level deep links.
    """
    graphql_query = """
    query SearchShow($searchQuery: String!, $country: Country!, $language: Language!) {
      popularTitles(
        country: $country
        filter: { searchQuery: $searchQuery, objectTypes: [SHOW] }
        first: 6
      ) {
        edges {
          node {
            id
            objectId
            objectType
            content(country: $country, language: $language) {
              title
              originalReleaseYear
              shortDescription
              runtime
              posterUrl
            }
            offers(country: $country, platform: WEB) {
              monetizationType
              standardWebURL
              package {
                shortName
                clearName
              }
            }
          }
        }
      }
    }
    """
    clean_title = strip_year_suffix(title)
    ref_titles = [clean_title, title] + [t for t in (alt_titles or []) if t]
    search_queries = [clean_title]
    for alt in alt_titles or []:
        alt_clean = strip_year_suffix(alt)
        if alt_clean and normalize_title_key(alt_clean) not in {
            normalize_title_key(q) for q in search_queries
        }:
            search_queries.append(alt_clean)
    if ":" in clean_title:
        prefix = clean_title.split(":", 1)[0].strip()
        if len(prefix) >= 8 and normalize_title_key(prefix) not in {
            normalize_title_key(q) for q in search_queries
        }:
            search_queries.append(prefix)

    best_node = None
    for sq in search_queries[:3]:
        payload = json.dumps(
            {
                "operationName": "SearchShow",
                "query": graphql_query,
                "variables": {
                    "searchQuery": sq,
                    "country": "US",
                    "language": "en",
                },
            }
        ).encode("utf-8")

        req = urllib.request.Request(
            JUSTWATCH_GRAPHQL_URL,
            data=payload,
            headers={
                "Content-Type": "application/json",
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except Exception as exc:
            print(f"  [JustWatch] Warning querying '{sq}': {exc}")
            continue

        edges = (
            data.get("data", {})
            .get("popularTitles", {})
            .get("edges", [])
        )
        if not edges:
            continue

        ref_norms = {normalize_title_key(strip_year_suffix(r)) for r in ref_titles if r}
        # Pass 1: exact normalized title match + target_year match
        for edge in edges:
            node = edge["node"]
            if node.get("objectType") != "SHOW":
                continue
            cand_content = node.get("content", {})
            cand_title = cand_content.get("title", "")
            cand_year = cand_content.get("originalReleaseYear")
            if normalize_title_key(cand_title) in ref_norms:
                if target_year is None or cand_year == target_year:
                    best_node = node
                    break
        if best_node:
            break

        # Pass 2: fuzzy/token title match + year match (if target_year or expected_year given)
        year_guard = target_year or expected_year
        for edge in edges:
            node = edge["node"]
            if node.get("objectType") != "SHOW":
                continue
            cand_content = node.get("content", {})
            cand_title = cand_content.get("title", "")
            cand_year = cand_content.get("originalReleaseYear")
            if titles_match(cand_title, ref_titles):
                if year_guard is None or (cand_year and abs(cand_year - year_guard) <= 1):
                    best_node = node
                    break
        if best_node:
            break

        # Pass 3: JustWatch sometimes returns Japanese phonetic/romaji display titles
        # (e.g. "Rikorisu rikoiru" for "Lycoris Recoil" or "Tefuda ga Ome no Bikutoria"
        # for "Victoria of Many Faces"). Accept if year matches expected_year and either
        # JustWatch returned a single hit or shares a distinctive token with ref_titles.
        if year_guard is not None:
            ref_distinct_tokens = {
                t
                for r in ref_titles
                if r
                for t in re.findall(r"[a-z0-9]+", strip_diacritics(r).lower())
                if len(t) >= 5 and t not in {"season", "series", "anime", "story", "world"}
            }
            for edge in edges[:2]:
                node = edge["node"]
                if node.get("objectType") != "SHOW":
                    continue
                cand_content = node.get("content", {})
                cand_title = cand_content.get("title", "")
                cand_year = cand_content.get("originalReleaseYear")
                if cand_year == year_guard:
                    cand_distinct = {
                        t
                        for t in re.findall(r"[a-z0-9]+", strip_diacritics(cand_title).lower())
                        if len(t) >= 5
                    }
                    if len(edges) == 1 or (cand_distinct & ref_distinct_tokens):
                        best_node = node
                        break
        if best_node:
            break

    if not best_node:
        return None

    content = best_node.get("content") or {}
    offers = best_node.get("offers") or []

    # Collect unique subscription/free/ad-supported streaming offers
    providers: dict[str, dict[str, Any]] = {}
    allowed_monetization = {"FLATRATE", "FREE", "ADS"}

    for offer in offers:
        m_type = offer.get("monetizationType")
        if m_type not in allowed_monetization:
            continue
        pkg = offer.get("package") or {}
        short_name = (pkg.get("shortName") or "").lower()
        clear_name = pkg.get("clearName") or ""
        web_url = offer.get("standardWebURL") or ""

        prov_key = JUSTWATCH_PROVIDER_MAP.get(short_name)
        if not prov_key:
            # Strictly ignore paid channel add-ons (e.g. 'cra' = Crunchyroll Amazon Channel)
            continue

        if prov_key not in providers and web_url:
            pkg_meta = ANDROID_TV_PACKAGES.get(prov_key, {})
            providers[prov_key] = {
                "id": prov_key,
                "name": pkg_meta.get("name", clear_name or prov_key.title()),
                "color": pkg_meta.get("color", "#4A5568"),
                "monetization": m_type.lower(),
                "webUrl": web_url,
                "androidTvIntentUrl": build_android_tv_intent(web_url, prov_key),
            }

    poster_path = content.get("posterUrl") or ""
    poster_url = f"https://images.justwatch.com{poster_path}" if poster_path.startswith("/") else poster_path

    node_id = best_node.get("id")
    episode_offers: dict[str, dict[str, str]] = {}
    if node_id and best_node.get("objectType") == "SHOW":
        episode_offers = query_justwatch_episode_offers(
            node_id=node_id,
            has_disney_plus="disney_plus" in providers,
        )

    return {
        "nodeId": node_id,
        "matchedTitle": content.get("title"),
        "year": content.get("originalReleaseYear"),
        "runtimeMinutes": content.get("runtime"),
        "posterUrl": poster_url,
        "shortDescription": content.get("shortDescription"),
        "streamingProviders": list(providers.values()),
        "episodeOffers": episode_offers,
    }


def query_justwatch_episode_offers(
    node_id: str,
    has_disney_plus: bool = False,
) -> dict[str, dict[str, str]]:
    """
    Fetches direct per-episode playback URLs across seasons from JustWatch so the
    'Roll Random Episode' feature can launch the exact rolled episode in 1 click.
    """
    graphql_query = """
    query GetShowEpisodes($id: ID!, $country: Country!, $language: Language!) {
      node(id: $id) {
        ... on Show {
          seasons {
            content(country: $country, language: $language) {
              seasonNumber
            }
            episodes {
              content(country: $country, language: $language) {
                seasonNumber
                episodeNumber
              }
              offers(country: $country, platform: WEB) {
                monetizationType
                standardWebURL
                package {
                  shortName
                }
              }
            }
          }
        }
      }
    }
    """
    payload = json.dumps(
        {
            "operationName": "GetShowEpisodes",
            "query": graphql_query,
            "variables": {
                "id": node_id,
                "country": "US",
                "language": "en",
            },
        }
    ).encode("utf-8")

    req = urllib.request.Request(
        JUSTWATCH_GRAPHQL_URL,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception as exc:
        print(f"  [JustWatch Episodes] Warning querying node '{node_id}': {exc}")
        return {}

    seasons = ((data.get("data") or {}).get("node") or {}).get("seasons") or []
    allowed_monetization = {"FLATRATE", "FREE", "ADS"}
    episode_offers: dict[str, dict[str, str]] = {}
    abs_counter = 0

    for season in seasons:
        s_default = (season.get("content") or {}).get("seasonNumber")
        for ep in season.get("episodes") or []:
            ep_content = ep.get("content") or {}
            s_num = ep_content.get("seasonNumber") or s_default
            e_num = ep_content.get("episodeNumber")
            if not s_num or not e_num:
                continue
            abs_counter += 1

            ep_links: dict[str, str] = {}
            for offer in ep.get("offers") or []:
                if offer.get("monetizationType") not in allowed_monetization:
                    continue
                short_name = ((offer.get("package") or {}).get("shortName") or "").lower()
                prov_key = JUSTWATCH_PROVIDER_MAP.get(short_name)
                if not prov_key or prov_key in ep_links:
                    continue
                raw_url = offer.get("standardWebURL") or ""
                clean_url = unwrap_affiliate_url(raw_url)
                if clean_url:
                    ep_links[prov_key] = clean_url

            # When a show streams on both Disney+ and Hulu, Hulu's /watch/<uuid>
            # maps directly to https://www.disneyplus.com/play/<uuid>
            if has_disney_plus and "hulu" in ep_links:
                m = re.search(r"/watch/([0-9a-fA-F-]{36})", ep_links["hulu"])
                if m:
                    ep_links["disney_plus"] = f"https://www.disneyplus.com/play/{m.group(1)}"

            if ep_links:
                episode_offers[f"{int(s_num)}:{int(e_num)}"] = ep_links
                episode_offers.setdefault(f"abs:{abs_counter}", ep_links)

    return episode_offers


ANILIST_SITE_MAP: dict[str, str] = {
    "crunchyroll": "crunchyroll",
    "netflix": "netflix",
    "hulu": "hulu",
    "hidive": "hidive",
    "amazon prime video": "prime_video",
    "disney plus": "disney_plus",
    "tubi tv": "tubi",
}


def query_anilist_metadata(title: str, target_year: int | None = None) -> dict[str, Any] | None:
    """
    Queries AniList GraphQL API for anime metadata, high-res cover art, romaji/english
    titles, official series-level streaming links (especially Crunchyroll /series/ hubs),
    and streaming episode lists.
    """
    graphql_query = """
    query SearchAnime($search: String) {
      Page(page: 1, perPage: 8) {
        media(search: $search, type: ANIME, sort: [SEARCH_MATCH, POPULARITY_DESC]) {
          id
          idMal
          format
          seasonYear
          startDate {
            year
          }
          duration
          episodes
          genres
          title {
            romaji
            english
            native
          }
          synonyms
          coverImage {
            extraLarge
            large
          }
          externalLinks {
            site
            url
            type
          }
          streamingEpisodes {
            title
            url
            site
          }
        }
      }
    }
    """
    search_str = strip_year_suffix(title)
    payload = json.dumps(
        {
            "query": graphql_query,
            "variables": {"search": search_str},
        }
    ).encode("utf-8")

    data = None
    for attempt in range(2):
        req = urllib.request.Request(
            ANILIST_GRAPHQL_URL,
            data=payload,
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
                "User-Agent": "RandomFlix/2.0",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=12) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            break
        except urllib.error.HTTPError as exc:
            if exc.code == 429 and attempt == 0:
                retry_after = int(exc.headers.get("Retry-After") or "15")
                print(f"  [AniList] Rate limited (429), sleeping {retry_after}s...")
                time.sleep(min(retry_after, 30))
                continue
            print(f"  [AniList] Warning querying '{title}': {exc}")
            return None
        except Exception as exc:
            print(f"  [AniList] Warning querying '{title}': {exc}")
            return None

    media_list = ((data or {}).get("data") or {}).get("Page", {}).get("media") or []
    if not media_list:
        return None

    # Filter to TV / ONA formats first if available
    tv_candidates = [
        m for m in media_list if m.get("format") in ("TV", "TV_SHORT", "ONA", None)
    ] or media_list

    target_norm = normalize_title_key(search_str)
    chosen = tv_candidates[0]

    # Prefer exact title + target_year match
    best_score = -1
    for idx, m in enumerate(tv_candidates):
        t_obj = m.get("title") or {}
        eng = t_obj.get("english") or ""
        rom = t_obj.get("romaji") or ""
        syns = m.get("synonyms") or []
        cand_norms = {normalize_title_key(s) for s in [eng, rom, *syns] if s}
        cand_year = m.get("seasonYear") or (m.get("startDate") or {}).get("year")

        score = 0
        if target_norm in cand_norms:
            score += 50
        elif titles_match(search_str, [eng, rom, *syns]):
            score += 25

        if target_year is not None:
            if cand_year == target_year:
                score += 40
            elif cand_year and abs(cand_year - target_year) <= 1:
                score += 10
            else:
                score -= 30
        else:
            # Prefer Season 1 / base series over sequels (2nd Season, Part 2, etc.)
            lower_names = f"{eng} {rom}".lower()
            if not re.search(r"\b(season\s*[2-9]|2nd\s*season|3rd\s*season|part\s*[2-9]|ii|iii)\b", lower_names):
                score += 10

        score -= idx  # tie-breaker: preserve search rank
        if score > best_score:
            best_score = score
            chosen = m

    t_obj = chosen.get("title") or {}
    year = chosen.get("seasonYear") or (chosen.get("startDate") or {}).get("year")
    cover = chosen.get("coverImage") or {}
    poster_url = cover.get("extraLarge") or cover.get("large") or ""

    ext_providers: dict[str, str] = {}
    for link in chosen.get("externalLinks") or []:
        if link.get("type") not in ("STREAMING", None):
            continue
        site = (link.get("site") or "").strip().lower()
        url = (link.get("url") or "").strip()
        prov_key = ANILIST_SITE_MAP.get(site)
        if not prov_key or not url:
            continue
        if url.startswith("http://www.crunchyroll.com/"):
            url = "https://" + url[len("http://") :]
        # Prefer /series/ URLs on Crunchyroll when multiple links exist
        if prov_key in ext_providers:
            if "/series/" in url and "/series/" not in ext_providers[prov_key]:
                ext_providers[prov_key] = url
        else:
            ext_providers[prov_key] = url

    # Parse streamingEpisodes for episode list fallback & direct Crunchyroll episode links
    ep_list: list[dict[str, Any]] = []
    cr_ep_offers: dict[str, str] = {}
    seen_eps: set[int] = set()
    for idx_ep, se in enumerate(chosen.get("streamingEpisodes") or [], start=1):
        raw_ep_title = (se.get("title") or "").strip()
        ep_url = (se.get("url") or "").strip()
        site = (se.get("site") or "").strip().lower()
        if ep_url.startswith("http://www.crunchyroll.com/"):
            ep_url = "https://" + ep_url[len("http://") :]

        m_ep = re.match(r"^Episode\s+(\d+)\s*[-–:]?\s*(.*)$", raw_ep_title, re.IGNORECASE)
        if m_ep:
            ep_num = int(m_ep.group(1))
            clean_ep_title = m_ep.group(2).strip() or f"Episode {ep_num}"
        else:
            ep_num = idx_ep
            clean_ep_title = raw_ep_title or f"Episode {ep_num}"

        if ep_num not in seen_eps:
            seen_eps.add(ep_num)
            ep_list.append({"ep": ep_num, "title": clean_ep_title})

        if site == "crunchyroll" and "/watch/" in ep_url:
            cr_ep_offers[f"1:{ep_num}"] = ep_url
            cr_ep_offers[f"abs:{ep_num}"] = ep_url

    ep_list.sort(key=lambda x: x["ep"])
    total_eps = chosen.get("episodes") or len(ep_list)
    if not ep_list and total_eps and int(total_eps) > 0:
        ep_list = [{"ep": i, "title": f"Episode {i}"} for i in range(1, int(total_eps) + 1)]

    seasons = [{"season": 1, "episodes": ep_list}] if ep_list else []

    return {
        "anilistId": chosen.get("id"),
        "malId": chosen.get("idMal"),
        "englishTitle": t_obj.get("english"),
        "romajiTitle": t_obj.get("romaji"),
        "year": year,
        "runtimeMinutes": chosen.get("duration") or 24,
        "genres": chosen.get("genres") or ["Anime"],
        "posterUrl": poster_url,
        "externalProviders": ext_providers,
        "crunchyrollEpisodeOffers": cr_ep_offers,
        "totalSeasons": 1 if seasons else 0,
        "totalEpisodes": len(ep_list),
        "seasons": seasons,
    }


def query_tvmaze_metadata(
    title: str,
    target_year: int | None = None,
    is_anime: bool = False,
    alt_titles: list[str] | None = None,
) -> dict[str, Any] | None:
    """Fetches TV show runtime, genres, poster, and episode guide from TVMaze."""
    clean_primary = strip_year_suffix(
        "Pokémon" if "pok" in title.lower() and "indigo" in title.lower() else title
    )
    candidates = [clean_primary]
    for alt in alt_titles or []:
        alt_clean = strip_year_suffix(alt)
        if alt_clean and normalize_title_key(alt_clean) not in {
            normalize_title_key(c) for c in candidates
        }:
            candidates.append(alt_clean)
    ref_titles = [clean_primary, title] + [t for t in (alt_titles or []) if t]

    data = None
    for search_title in candidates:
        cand_data = None
        if target_year is not None:
            # Disambiguate across multiple TVMaze matches by release year
            search_url = f"https://api.tvmaze.com/search/shows?{urllib.parse.urlencode({'q': search_title})}"
            try:
                req = urllib.request.Request(search_url, headers={"User-Agent": "RandomFlix/2.0"})
                with urllib.request.urlopen(req, timeout=10) as resp:
                    results = json.loads(resp.read().decode("utf-8"))
                chosen_id = None
                for r in results:
                    sh = r.get("show") or {}
                    prem = (sh.get("premiered") or "")[:4]
                    if prem.isdigit() and int(prem) == target_year:
                        if is_anime and sh.get("type") != "Animation" and "Anime" not in (sh.get("genres") or []):
                            continue
                        chosen_id = sh.get("id")
                        break
                if chosen_id:
                    url = f"https://api.tvmaze.com/shows/{chosen_id}?embed=episodes"
                else:
                    params = urllib.parse.urlencode({"q": search_title, "embed": "episodes"})
                    url = f"{TVMAZE_SEARCH_URL}?{params}"
            except Exception:
                params = urllib.parse.urlencode({"q": search_title, "embed": "episodes"})
                url = f"{TVMAZE_SEARCH_URL}?{params}"
        else:
            params = urllib.parse.urlencode({"q": search_title, "embed": "episodes"})
            url = f"{TVMAZE_SEARCH_URL}?{params}"

        req = urllib.request.Request(
            url,
            headers={"User-Agent": "RandomFlix/2.0"},
        )
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                cand_data = json.loads(resp.read().decode("utf-8"))
        except Exception:
            cand_data = None

        if not cand_data:
            continue

        # Validate that an anime query did not fuzzy-match a live-action Western show
        if is_anime:
            show_type = cand_data.get("type") or ""
            show_genres = cand_data.get("genres") or []
            if show_type != "Animation" and "Anime" not in show_genres:
                continue
            cand_name = cand_data.get("name") or ""
            if not titles_match(cand_name, ref_titles):
                continue

        data = cand_data
        break

    if not data:
        return None

    image = data.get("image") or {}
    poster_url = image.get("original") or image.get("medium") or ""
    premiered = data.get("premiered") or ""
    year = int(premiered[:4]) if len(premiered) >= 4 and premiered[:4].isdigit() else None
    runtime = data.get("averageRuntime") or data.get("runtime")
    genres = data.get("genres") or []

    # Build compact episode guide grouped by season (for opt-in random episode picker)
    raw_episodes = data.get("_embedded", {}).get("episodes", [])
    seasons_map: dict[int, list[dict[str, Any]]] = {}
    total_episodes = 0
    for ep in raw_episodes:
        s_num = ep.get("season")
        e_num = ep.get("number")
        ep_title = ep.get("name") or f"Episode {e_num}"
        if not s_num or not e_num:
            continue
        seasons_map.setdefault(int(s_num), []).append(
            {"ep": int(e_num), "title": ep_title}
        )
        total_episodes += 1

    seasons_list = [
        {"season": s_num, "episodes": eps}
        for s_num, eps in sorted(seasons_map.items())
    ]

    return {
        "year": year,
        "runtimeMinutes": runtime,
        "genres": genres,
        "posterUrl": poster_url,
        "totalSeasons": len(seasons_list),
        "totalEpisodes": total_episodes,
        "seasons": seasons_list,
    }


def classify_show_strict(
    entry: dict[str, Any],
    genres: list[str],
    runtime_minutes: int | None,
) -> tuple[int, str, str]:
    """
    Applies the strict RandomFlix 2.0 categorization rules:
      - Category 1 (Watched): User has already watched it (`watched: true` or `category == 1`).
        Always safe for background viewing or comfort rewatching.
      - Category 2 (True Background / Episodic): Unwatched shows that pass the strict
        "Couch Doze-Off Test" (sitcoms, workplace/animated comedies, procedural case-of-the-week,
        food/travel/sketch/anthology).
      - Category 3 (Active / Serialized): Unwatched plot-driven, serialized, mystery-box,
        or high-attention shows that must be watched sequentially with full attention.
    """
    raw_reason = entry.get("categoryReason") or ""
    if raw_reason.startswith("Assigned to Category"):
        raw_reason = ""

    if entry.get("watched") is True or entry.get("category") == 1:
        reason = raw_reason or "Already watched — safe for background or comfort rewatch anytime."
        serialization = entry.get("serialization") or "watched-comfort"
        return 1, reason, serialization

    if entry.get("category") in (2, 3) and raw_reason:
        cat = int(entry["category"])
        serialization = entry.get("serialization") or ("episodic" if cat == 2 else "serialized")
        return cat, raw_reason, serialization

    if entry.get("category") in (2, 3):
        cat = int(entry["category"])
        serialization = entry.get("serialization") or ("episodic" if cat == 2 else "serialized")
        default_reason = (
            "Episodic / low-stakes series — easy to drop in for background viewing."
            if cat == 2
            else "Serialized or plot-heavy series — requires full attention and sequential viewing."
        )
        return cat, default_reason, serialization

    # Strict heuristic fallback if no explicit LLM classification is present on the entry
    lower_genres = {g.lower() for g in genres}
    is_comedy = "comedy" in lower_genres
    is_heavy = bool(lower_genres & {"drama", "thriller", "mystery", "crime", "science-fiction", "fantasy", "action"})
    is_short = (runtime_minutes or 30) <= 30

    if is_comedy and is_short and not ("drama" in lower_genres and "mystery" in lower_genres):
        return (
            2,
            "Short-form episodic comedy — passes the Couch Doze-Off Test for low-stakes viewing.",
            "episodic",
        )
    if is_heavy:
        return (
            3,
            "Serialized or plot-heavy series — requires full attention and sequential viewing.",
            "serialized",
        )
    return (
        2 if is_short else 3,
        "Classified by episode structure and attention requirements.",
        "episodic" if is_short else "serialized",
    )


def enrich_all(force_refresh: bool = False) -> dict[str, Any]:
    if not SOURCE_PATH.exists():
        raise FileNotFoundError(f"Source file not found: {SOURCE_PATH}")

    source_data = json.loads(SOURCE_PATH.read_text(encoding="utf-8"))
    shows_input: list[dict[str, Any]] = source_data.get("shows", [])

    cache: dict[str, Any] = {}
    if CACHE_PATH.exists() and not force_refresh:
        try:
            cache = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
        except Exception:
            cache = {}

    legacy_lookup = load_legacy_csv_lookup()
    catalog_shows: list[dict[str, Any]] = []

    for idx, item in enumerate(shows_input, start=1):
        title = item["title"].strip()
        norm_key = normalize_title_key(title)
        is_anime = item.get("mediaType") == "anime" or bool(item.get("isAnime"))
        is_disabled = bool(item.get("disabled", False))
        status_tag = " [DISABLED]" if is_disabled else ""
        print(f"[{idx}/{len(shows_input)}] Enriching '{title}'{status_tag}...")

        cached = cache.get(norm_key, {})
        jw_data = cached.get("justwatch")
        tvm_data = cached.get("tvmaze")
        anilist_data = cached.get("anilist")

        target_year = item.get("year")
        western_anime_ids = {"castlevania", "thelegendofkorra"}

        if (
            is_anime
            and norm_key not in western_anime_ids
            and (anilist_data is None or force_refresh)
        ):
            anilist_data = query_anilist_metadata(title, target_year=target_year)
            time.sleep(0.6)

        alt_titles: list[str] = []
        if anilist_data:
            for k in ("englishTitle", "romajiTitle"):
                val = anilist_data.get(k)
                if val and val not in alt_titles:
                    alt_titles.append(val)

        expected_year = target_year or (anilist_data or {}).get("year")

        if (
            jw_data is None
            or force_refresh
            or (jw_data is not None and "episodeOffers" not in jw_data)
            or (target_year and jw_data and jw_data.get("year") != target_year)
            or (
                expected_year
                and jw_data
                and jw_data.get("year")
                and abs(jw_data["year"] - expected_year) > 2
            )
        ):
            jw_data = query_justwatch_us(
                title,
                target_year=target_year,
                alt_titles=alt_titles,
                expected_year=expected_year,
            )
            time.sleep(0.25)

        # If AniList missed an English-only title (e.g. "Aharen-san Is Indecipherable")
        # and JustWatch matched its Romaji title ("Aharen-san wa Hakarenai"), retry AniList with that title.
        if (
            is_anime
            and norm_key not in western_anime_ids
            and anilist_data is None
            and jw_data
            and jw_data.get("matchedTitle")
        ):
            anilist_data = query_anilist_metadata(
                jw_data["matchedTitle"], target_year=target_year
            )
            time.sleep(0.5)
            if anilist_data:
                for k in ("englishTitle", "romajiTitle"):
                    val = anilist_data.get(k)
                    if val and val not in alt_titles:
                        alt_titles.append(val)

        if jw_data and jw_data.get("matchedTitle") and jw_data["matchedTitle"] not in alt_titles:
            alt_titles.append(jw_data["matchedTitle"])

        if (
            (tvm_data is None and ("tvmaze" not in cached or alt_titles))
            or force_refresh
            or (target_year and tvm_data and tvm_data.get("year") != target_year)
        ):
            tvm_data = query_tvmaze_metadata(
                title,
                target_year=target_year,
                is_anime=is_anime,
                alt_titles=alt_titles,
            )
            time.sleep(0.25)

        cache[norm_key] = {
            "justwatch": jw_data,
            "tvmaze": tvm_data,
            "anilist": anilist_data,
            "updatedAt": datetime.now(timezone.utc).isoformat(),
        }
        if idx % 10 == 0:
            CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
            CACHE_PATH.write_text(json.dumps(cache, indent=2), encoding="utf-8")

        legacy_info = legacy_lookup.get(norm_key, {})
        anilist_providers = (anilist_data or {}).get("externalProviders") or {}
        al_cr_ep_offers: dict[str, str] = (
            (anilist_data or {}).get("crunchyrollEpisodeOffers") or {}
        )

        # Merge streaming providers and sanitize all links to series-level hubs
        raw_providers = (jw_data or {}).get("streamingProviders") or []
        providers = normalize_providers_list(
            raw_providers,
            norm_key,
            title,
            legacy_info,
            item,
            anilist_providers=anilist_providers,
            anilist_ep_offers=al_cr_ep_offers,
        )

        genres = (
            item.get("genres")
            or (tvm_data or {}).get("genres")
            or (anilist_data or {}).get("genres")
            or []
        )
        runtime = (
            item.get("runtimeMinutes")
            or (tvm_data or {}).get("runtimeMinutes")
            or (anilist_data or {}).get("runtimeMinutes")
            or (jw_data or {}).get("runtimeMinutes")
            or (24 if is_anime else 30)
        )
        year = (
            item.get("year")
            or (tvm_data or {}).get("year")
            or (anilist_data or {}).get("year")
            or (jw_data or {}).get("year")
        )
        jw_poster = ((jw_data or {}).get("posterUrl") or "").replace(
            "{profile}", "s592"
        ).replace("{format}", "webp")
        poster_url = (
            item.get("posterUrl")
            or (tvm_data or {}).get("posterUrl")
            or (anilist_data or {}).get("posterUrl")
            or jw_poster
            or ""
        )

        category, category_reason, serialization = classify_show_strict(
            item, genres, runtime
        )

        raw_vibe = item.get("vibe") or ""
        if raw_vibe.startswith("Added from the Manage Shows"):
            raw_vibe = ""
        vibe = (
            raw_vibe
            or (jw_data or {}).get("shortDescription")
            or "Ready to stream in your RandomFlix rotation."
        )
        media_type = item.get("mediaType") or (
            "anime" if "Anime" in genres or item.get("isAnime") else "tv"
        )
        allow_random_episode = item.get(
            "allowRandomEpisode",
            category in (1, 2) and serialization in ("watched-comfort", "episodic"),
        )

        raw_seasons = (
            (tvm_data or {}).get("seasons")
            or (anilist_data or {}).get("seasons")
            or []
        )
        episode_offers: dict[str, dict[str, str]] = (jw_data or {}).get("episodeOffers") or {}
        al_cr_ep_offers: dict[str, str] = (
            (anilist_data or {}).get("crunchyrollEpisodeOffers") or {}
        )
        active_provider_ids = {p["id"] for p in providers}
        series_url_by_provider = {p["id"]: p["webUrl"] for p in providers}

        seasons: list[dict[str, Any]] = []
        abs_ep_idx = 0
        for s_obj in raw_seasons:
            s_num = s_obj.get("season")
            enriched_eps: list[dict[str, Any]] = []
            for ep_obj in s_obj.get("episodes") or []:
                e_num = ep_obj.get("ep")
                abs_ep_idx += 1
                raw_links = dict(
                    episode_offers.get(f"{s_num}:{e_num}")
                    or episode_offers.get(f"abs:{abs_ep_idx}")
                    or {}
                )
                if "crunchyroll" not in raw_links:
                    al_cr_ep = al_cr_ep_offers.get(f"{s_num}:{e_num}") or al_cr_ep_offers.get(
                        f"abs:{abs_ep_idx}"
                    )
                    if al_cr_ep:
                        raw_links["crunchyroll"] = al_cr_ep

                if "disney_plus" in active_provider_ids and "hulu" in raw_links:
                    m = re.search(r"/watch/([0-9a-fA-F-]{36})", raw_links["hulu"])
                    if m:
                        raw_links["disney_plus"] = f"https://www.disneyplus.com/play/{m.group(1)}"

                cr_ep_override = CRUNCHYROLL_EPISODE_OVERRIDES.get(norm_key, {}).get(abs_ep_idx)
                if cr_ep_override and "crunchyroll" in active_provider_ids:
                    raw_links["crunchyroll"] = cr_ep_override

                # Keep only true per-episode playback URLs (exclude series-level URLs & defunct Funimation GE0000* IDs)
                filtered_links = {
                    prov_id: url
                    for prov_id, url in raw_links.items()
                    if prov_id in active_provider_ids
                    and url != series_url_by_provider.get(prov_id)
                    and "/browse/entity-" not in url
                    and "netflix.com/title/" not in url
                    and "/watch/GE000" not in url
                }
                ep_entry: dict[str, Any] = {
                    "ep": e_num,
                    "title": ep_obj.get("title") or f"Episode {e_num}",
                }
                if filtered_links:
                    ep_entry["links"] = filtered_links
                enriched_eps.append(ep_entry)
            seasons.append({"season": s_num, "episodes": enriched_eps})

        total_seasons = (
            (tvm_data or {}).get("totalSeasons")
            or (anilist_data or {}).get("totalSeasons")
            or len(seasons)
        )
        total_episodes = (
            (tvm_data or {}).get("totalEpisodes")
            or (anilist_data or {}).get("totalEpisodes")
            or sum(len(s.get("episodes", [])) for s in seasons)
        )

        catalog_shows.append(
            {
                "id": norm_key,
                "title": title,
                "disabled": is_disabled,
                "category": category,
                "watched": category == 1 or bool(item.get("watched")),
                "mediaType": media_type,
                "serialization": serialization,
                "allowRandomEpisode": allow_random_episode,
                "year": year,
                "pinnedYear": item.get("year"),
                "runtimeMinutes": runtime,
                "genres": genres,
                "moodTags": item.get("moodTags") or [],
                "vibe": vibe,
                "categoryReason": category_reason,
                "posterUrl": poster_url,
                "streamingProviders": providers,
                "googleTvSearchUrl": f"https://www.google.com/search?q={urllib.parse.quote(title + ' tv show watch')}",
                "totalSeasons": total_seasons,
                "totalEpisodes": total_episodes,
                "seasons": seasons,
            }
        )

    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    CACHE_PATH.write_text(json.dumps(cache, indent=2), encoding="utf-8")

    active_shows = [s for s in catalog_shows if not s.get("disabled")]
    disabled_count = len(catalog_shows) - len(active_shows)

    catalog_payload = {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "totalShows": len(active_shows),
        "totalInList": len(catalog_shows),
        "disabledShows": disabled_count,
        "countsByCategory": {
            "1_watched": sum(1 for s in active_shows if s["category"] == 1),
            "2_background": sum(1 for s in active_shows if s["category"] == 2),
            "3_active": sum(1 for s in active_shows if s["category"] == 3),
        },
        "shows": catalog_shows,
    }

    CATALOG_OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    CATALOG_OUT_PATH.write_text(json.dumps(catalog_payload, indent=2), encoding="utf-8")
    print(
        f"\nSaved {len(active_shows)} active shows ({disabled_count} disabled, {len(catalog_shows)} total) to {CATALOG_OUT_PATH} "
        f"(Cat 1: {catalog_payload['countsByCategory']['1_watched']}, "
        f"Cat 2: {catalog_payload['countsByCategory']['2_background']}, "
        f"Cat 3: {catalog_payload['countsByCategory']['3_active']})"
    )
    return catalog_payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Enrich RandomFlix show catalog")
    parser.add_argument(
        "--refresh",
        action="store_true",
        help="Force fresh API lookups from JustWatch and TVMaze",
    )
    args = parser.parse_args()
    enrich_all(force_refresh=args.refresh)


if __name__ == "__main__":
    main()
