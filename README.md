# rivalsdata-api

An unofficial Python client for public player data on
[RivalsData](https://rivalsdata.com). It is an early, community-maintained
package built against undocumented endpoints. RivalsData may change those
endpoints or their response formats without notice.

## Install

Python 3.10 or newer is required. Use a virtual environment to keep the
package's dependencies separate from other Python tools:

```console
python -m venv .venv
# Windows PowerShell
.venv\Scripts\Activate.ps1
# macOS or Linux
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install rivalsdata-api
```

Until the package is published to PyPI, install it from a source checkout by
replacing the last command with `python -m pip install .`. For editable
development, use `python -m pip install -e '.[dev]'`.

Camoufox is an optional Cloudflare fallback:

```console
python -m pip install 'rivalsdata-api[browser]'
python -m camoufox fetch
```

## Quick start

```python
from rivalsdata import RivalsDataClient

with RivalsDataClient() as client:
    by_uid = client.get_player(1970288503)
    by_name = client.get_player("GS-")
    search_result = client.resolve_player("GS-")

print(by_name["name"], by_name["uid"], by_name["level"])
```

The client supports context-manager usage and closes its HTTP session when the
block exits. It returns dictionaries containing the fields RivalsData returns;
fields can vary by player and may change over time.

### Methods

- `resolve_player(username)` searches by name and returns the top matching
  RivalsData search result, with a numeric `uid` added.
- `get_player(uuid_or_username)` accepts either a numeric UID or a username,
  resolves names, then fetches the profile.
- `get_player_by_uid(uid)` fetches a profile from a numeric UID.

### Cloudflare fallback

Requests use curl_cffi with a Chrome TLS profile by default. If Cloudflare
blocks the request, install the browser extra and set the fallback option:

```python
from rivalsdata import RivalsDataClient

with RivalsDataClient(use_browser_fallback=True) as client:
    player = client.get_player(1970288503)
```

Camoufox opens a headless browser, loads RivalsData, and retries the same
public API request from that browser context. The first Camoufox setup also
requires `python -m camoufox fetch`.

### Errors

All package errors inherit from `RivalsDataError`:

- `PlayerNotFoundError`: no profile or search result was found.
- `CloudflareError`: Cloudflare blocked the request, or Camoufox could not
  complete it.
- `RivalsDataHTTPError`: RivalsData returned an unsuccessful response or
  unexpected data.

## Development and contribution

See [CONTRIBUTING.md](CONTRIBUTING.md) for environment setup, workflow, and
project-specific implementation notes. For a compact handoff to a new
contributor or coding session, see [docs/PROJECT_CONTEXT.md](docs/PROJECT_CONTEXT.md).

This project is not affiliated with RivalsData, NetEase, or Marvel. Please
respect the site's terms and keep request rates reasonable.
