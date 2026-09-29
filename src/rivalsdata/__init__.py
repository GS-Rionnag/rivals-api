"""Unofficial client for public RivalsData player data."""

from .client import RivalsDataClient
from .exceptions import (
    CloudflareError,
    PlayerNotFoundError,
    RivalsDataError,
    RivalsDataHTTPError,
)
from .models import DataModel, Player, StatRecord
from .hero_ids import HERO_NAMES, hero_id, hero_name

__all__ = [
    "CloudflareError",
    "DataModel",
    "HERO_NAMES",
    "Player",
    "PlayerNotFoundError",
    "RivalsDataClient",
    "RivalsDataError",
    "RivalsDataHTTPError",
    "StatRecord",
    "hero_id",
    "hero_name",
]
__version__ = "0.2.0"
