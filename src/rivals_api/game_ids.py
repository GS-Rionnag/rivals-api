"""Offline labels verified against the providers' public catalogs (2026-10-02).

Map IDs identify variants, not just locations. Gameplay codes are deliberately
not mapped globally: the objective name comes from the particular map variant.
"""

import json
from importlib.resources import files
from typing import Any

CATALOG = json.loads(files(__package__).joinpath("game_catalog.json").read_text(encoding="utf-8"))
MAPS = CATALOG["maps"]
SEASONS = CATALOG["seasons"]
GAME_MODES = {1: "Quick Match", 2: "Competitive", 3: "Custom", 4: "Arcade",
              5: "Tutorial", 7: "Practice vs AI", 9: "Tournament", 10: "Tournament"}
# RivalsData calls code 6 Duel; RivalsTracker calls it Practice. Keep the
# source's interpretation rather than pretending those labels are agreed.
MODE_SIX = {"rivalsdata": "Duel", "rivalstracker": "Practice"}
PLATFORMS = {1: "PC", 2: "PlayStation", 4: "Xbox"}
PLATFORM_ALIASES = {"pc": 1, "windows": 1, "playstation": 2, "psn": 2,
                    "ps5": 2, "xbox": 4, "xbl": 4}


def numeric_id(value: Any) -> int | None:
    """Accept integer codes and their JSON string form without truncating."""
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.strip().isdecimal():
        return int(value)
    return None


def rank_label(value: Any) -> tuple[str | None, str | None, int | None]:
    level = numeric_id(value)
    if level == 0:
        return "Unranked", "Unranked", None
    if level is not None and 1 <= level <= 21:
        tier = ("Bronze", "Silver", "Gold", "Platinum", "Diamond", "Grandmaster", "Celestial")[(level - 1) // 3]
        division = 3 - (level - 1) % 3
        return f"{tier} {division}", tier, division
    if level == 22:
        return "Eternity", "Eternity", None
    if level is not None and 23 <= level <= 25:
        return "One Above All", "One Above All", None
    return None, None, None
