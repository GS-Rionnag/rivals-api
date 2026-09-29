"""Unofficial client for public RivalsData player data."""

from .client import RivalsDataClient
from .exceptions import (
    CloudflareError,
    PlayerNotFoundError,
    RivalsDataError,
    RivalsDataHTTPError,
)
from .models import DataModel, Player, StatRecord

__all__ = [
    "CloudflareError",
    "DataModel",
    "Player",
    "PlayerNotFoundError",
    "RivalsDataClient",
    "RivalsDataError",
    "RivalsDataHTTPError",
    "StatRecord",
]
__version__ = "0.2.0"
