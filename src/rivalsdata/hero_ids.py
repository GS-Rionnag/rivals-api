"""Human-readable names for Marvel Rivals playable hero IDs.

Unknown IDs are intentionally left unresolved rather than guessed. The roster
is maintained from the current public hero directory at https://psylocke.gg/heroes.
"""

HERO_NAMES: dict[str, str] = {
    "1011": "Hulk",
    "1014": "The Punisher",
    "1015": "Storm",
    "1016": "Loki",
    "1017": "Human Torch",
    "1018": "Doctor Strange",
    "1020": "Mantis",
    "1021": "Hawkeye",
    "1022": "Captain America",
    "1023": "Rocket Raccoon",
    "1024": "Hela",
    "1025": "Cloak & Dagger",
    "1026": "Black Panther",
    "1027": "Groot",
    "1028": "Ultron",
    "1029": "Magik",
    "1030": "Moon Knight",
    "1031": "Luna Snow",
    "1032": "Squirrel Girl",
    "1033": "Black Widow",
    "1034": "Iron Man",
    "1035": "Venom",
    "1036": "Spider-Man",
    "1037": "Magneto",
    "1038": "Scarlet Witch",
    "1039": "Thor",
    "1040": "Mister Fantastic",
    "1041": "Winter Soldier",
    "1042": "Peni Parker",
    "1043": "Star-Lord",
    "1044": "Blade",
    "1045": "Namor",
    "1046": "Adam Warlock",
    "1047": "Jeff the Land Shark",
    "1048": "Psylocke",
    "1049": "Wolverine",
    "1050": "Invisible Woman",
    "1051": "The Thing",
    "1052": "Iron Fist",
    "1053": "Emma Frost",
    "1054": "Phoenix",
    "1055": "Angela",
    "1056": "Daredevil",
    "1057": "Deadpool",
    "1058": "Gambit",
    "1059": "Elsa Bloodstone",
    "1060": "White Fox",
    "1061": "Black Cat",
    "1062": "Devil Dinosaur",
    "1063": "Cyclops",
    "1064": "Jubilee",
    "1065": "Rogue",
    "1066": "The Hood",
    "1067": "Gorr the God Butcher",
}


def hero_name(hero_id: object) -> str | None:
    """Resolve a known playable hero ID, preserving unknown IDs for callers."""
    if hero_id is None:
        return None
    return HERO_NAMES.get(str(hero_id))


def hero_id(name: object) -> int | None:
    """Resolve a hero name case-insensitively; return ``None`` if unknown."""
    if name is None:
        return None
    wanted = " ".join(str(name).casefold().split())
    for identifier, hero in HERO_NAMES.items():
        if " ".join(hero.casefold().split()) == wanted:
            return int(identifier)
    return None
