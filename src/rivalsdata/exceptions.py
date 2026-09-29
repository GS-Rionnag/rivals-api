"""Exceptions raised by the RivalsData client."""

class RivalsDataError(Exception):
    """Base exception for client errors."""

class RivalsDataHTTPError(RivalsDataError):
    """The site returned an unsuccessful HTTP response."""

class CloudflareError(RivalsDataError):
    """Cloudflare blocked the HTTP client; use the optional browser extra."""

class PlayerNotFoundError(RivalsDataError):
    """No player matched the supplied UID or username."""
