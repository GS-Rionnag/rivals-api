"""Unofficial client for public RivalsData player data."""

from .client import RivalsDataClient
from .exceptions import (
    CloudflareError,
    PlayerNotFoundError,
    RivalsDataError,
    RivalsDataHTTPError,
)

__all__ = [
    "CloudflareError",
    "PlayerNotFoundError",
    "RivalsDataClient",
    "RivalsDataError",
    "RivalsDataHTTPError",
]
__version__ = "0.1.0"
