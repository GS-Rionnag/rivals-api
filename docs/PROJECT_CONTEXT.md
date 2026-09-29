# Project context for new contributors and coding sessions

## Objective

Build an unofficial, small Python package for reading public player profile
data from rivalsdata.com. The first feature is player lookup by numeric UID or
username. The public website is the source of truth for API behavior; its
backend API is undocumented and may change.

## Current package state

- Distribution name: `rivalsdata-api`
- Import name: `rivalsdata`
- Version: `0.1.0`
- Python: `>=3.10`
- Build backend: Hatchling, with a src layout
- Runtime dependency: curl_cffi
- Optional browser fallback: Camoufox
- Public client class: `RivalsDataClient`

The user-facing setup and examples live in README.md. Contribution instructions
live in CONTRIBUTING.md.

## Observed API behavior

The site profile page used during implementation was
`https://rivalsdata.com/player/1471250983`. Browser inspection exposed these
requests:

1. `POST https://api.rivalsdata.com/players/search`
   - JSON payload: `{"name": "GS-"}`
   - Example result: `{"aid":"11001_1970288503", "name":"GS-", ...}`
   - The last underscore-separated section of `aid` is a numeric UID.
2. `POST https://api.rivalsdata.com/player`
   - JSON payload: `{"uid": 1970288503}`
   - Returns a profile dictionary with keys such as `uid`, `name`,
     `level`, `faction`, `rank_game_season`, `status`, and `xp`.

Both endpoints were manually verified with curl_cffi Chrome impersonation.
The package was also manually exercised through both UID and username flows.
The optional Camoufox browser POST path was separately exercised successfully.

The page loads additional endpoints for heroes, crosshairs, matches, and other
profile sections. They are not part of the current public package API.

## Implementation notes

- `resolve_player(name)` calls `/players/search`, prefers a
  Unicode-normalized exact name match, and otherwise returns the first
  suggestion. RivalsData search results may be ambiguous; preserve that behavior
  unless there is a stronger observed signal for identifying the intended row.
- `get_player(value)` treats digit-only inputs as UIDs; all other strings are
  searched as usernames, then fetched from `/player`.
- `get_player_by_uid(uid)` requires digits only.
- Public errors are defined in `src/rivalsdata/exceptions.py`.
- The client does not yet expose typed models, async support, retries, caching,
  rate limiting, or separate hero/match APIs.

## Maintaining a clean Python setup

Use a virtual environment in the repository and install only needed extras:

```console
python -m venv .venv
python -m pip install -e '.[dev]'
```

Add `[browser]` only to develop or use the Camoufox fallback. Do not pin or
downgrade global packages to satisfy unrelated applications. The shared host
Python has unrelated conflicts involving Pyppeteer, Selenium, Google GenAI,
and Instructor; these are not dependencies of this package.

## Good next steps

- Add mocked unit tests for UID validation, search result parsing, HTTP errors,
  and Cloudflare fallback behavior.
- Improve search disambiguation while matching the website's actual behavior.
- Add additional profile-section methods only after capturing and documenting
  their request and response contracts from the public UI.
- Consider typed result models only after the response shape has stabilized.

Keep this document current whenever the package's interface or observed
upstream behavior changes. A new coding session should read this file,
CONTRIBUTING.md, and the relevant source files before editing.
