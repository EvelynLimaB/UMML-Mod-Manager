from __future__ import annotations

SUPPORTED_REGIONS = ("global", "japan", "taiwan", "korea")

_ALIASES = {
    "global": "global",
    "steam global": "global",
    "international": "global",
    "en": "global",
    "japan": "japan",
    "japanese": "japan",
    "jp": "japan",
    "taiwan": "taiwan",
    "taiwanese": "taiwan",
    "tw": "taiwan",
    "korea": "korea",
    "korean": "korea",
    "kr": "korea",
}


def normalize_region(value: str, *, default: str = "global") -> str:
    text = str(value or "").strip().casefold()
    return _ALIASES.get(text, text or default)


def legacy_region(value: str) -> str:
    normalized = normalize_region(value)
    return {
        "global": "Global",
        "japan": "Japan",
        "taiwan": "Taiwan",
        "korea": "Korea",
    }.get(normalized, str(value))


def region_from_game_name(value: str) -> str:
    """Infer the provider region without treating plain Japanese listings as global."""

    text = str(value or "").strip().casefold()
    if "global" in text or "international" in text:
        return "global"
    if "taiwan" in text:
        return "taiwan"
    if "korea" in text:
        return "korea"
    if "japan" in text or "japanese" in text:
        return "japan"
    # GameBanana's original Japanese game is often named only "Umamusume
    # Pretty Derby". The Global listing includes an explicit Global marker.
    if "pretty derby" in text:
        return "japan"
    return ""
