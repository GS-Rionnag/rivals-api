# Contributing

Thanks for helping improve rivalsdata-api. The client relies on undocumented
RivalsData endpoints, so contributions should keep requests conservative and
record how endpoint behavior was observed.

## Development setup

Use an isolated virtual environment:

```console
python -m venv .venv
# Windows PowerShell
.venv\Scripts\Activate.ps1
# macOS or Linux
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e '.[dev]'
```

Install the optional browser dependencies only when working on Camoufox:

```console
python -m pip install -e '.[browser,dev]'
python -m camoufox fetch
```

The browser extra does not include GeoIP support because the project does not
need geographic spoofing. A virtual environment also prevents this package's
dependencies from changing unrelated applications installed in system Python.

## Project map

- `src/rivalsdata/client.py`: HTTP client, username resolution, UID lookup,
  shared GET/POST handling, and the optional Camoufox retry.
- `src/rivalsdata/models.py`: mapping-compatible response models and the typed
  `Player` wrapper.
- `src/rivalsdata/resources.py`: lazy player and site-wide endpoint resources.
- `src/rivalsdata/exceptions.py`: public exception types.
- `src/rivalsdata/__init__.py`: package exports and version.
- `pyproject.toml`: build backend, package metadata, runtime and optional
  dependencies.
- `docs/API.md`: observed site sections, endpoint inventory, response samples,
  and open questions.
- `docs/PROJECT_CONTEXT.md`: contributor and new-chat handoff notes.

## How the client currently works

The client uses curl_cffi with browser TLS impersonation against
`https://api.rivalsdata.com`:

- `POST /players/search` with JSON `{"name": "..."}` returns search
  suggestions. Search records include an `aid`, such as
  `11001_1970288503`; the final numeric segment is the profile UID.
- `POST /player` with JSON `{"uid": 1970288503}` returns a typed `Player`
  object. Profile keys work as both mapping values and attributes.
- Resource managers cover public leaderboard, hero, team-up, insight, faction,
  match, and player-tab endpoints. See `docs/API.md` for the current inventory.
- If these requests are blocked and `use_browser_fallback=True`, the client
  loads RivalsData in Camoufox and retries the POST from the page context.

These are observed implementation details, not a supported RivalsData contract.
Do not assume that `aid` formats, filters, routes, or JSON fields are permanent.

## Contribution workflow

1. Check the existing public API and exception behavior before changing it.
2. Keep changes focused, typed, and documented. Avoid adding new runtime
   dependencies unless the feature needs them.
3. For endpoint changes, note the page or action that exposed the route and
   the request shape. Never commit cookies, tokens, or browser profile data.
4. Add or update automated tests for behavior changes. Keep network-dependent
   checks opt-in; routine tests should use mocked HTTP responses. The initial
   repository does not yet include an automated test suite.
5. Run the checks for the code you changed:

   ```console
   python -m pytest
   ruff check .
   python -m build
   ```

6. Update the README and project context if user-facing methods, dependencies,
   routes, or setup steps changed.

There is no live API compatibility guarantee. If RivalsData changes a route,
prefer a clear typed error over returning an empty profile or silently
mislabeling a search result.
