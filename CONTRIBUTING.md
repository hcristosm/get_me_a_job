# Contributing

## Dev setup

```bash
python3 -m venv .venv && .venv/bin/pip install -e '.[dev]'
.venv/bin/pytest -q
```

Tests never touch the network: sources are tested against JSON fixtures in `tests/fixtures/` through `httpx.MockTransport` (see `mock_client` in `tests/conftest.py`), and LLM calls use `FakeLLM`.

## Adding a job source

1. Create `src/gmaj/sources/<name>.py` with:

   ```python
   def fetch(track: Track, client: httpx.Client, settings: Settings) -> list[Job]: ...
   ```

   - Board-style sources read company slugs from `track.companies["<name>"]`.
   - Search-style sources use `search_terms(track)` (the track's `queries`, or its top keywords).
   - Call `resp.raise_for_status()`: the pipeline records the error and keeps going with the other sources.
   - Turn HTML descriptions into text with `html_to_text`, and map work mode with `remote_kind`.
2. Register it in `SOURCES` in `src/gmaj/sources/__init__.py`.
3. Record a fixture with 2 real jobs (trim long descriptions) in `tests/fixtures/<name>.json` and add a test like the ones in `tests/test_sources_*.py`.

Rules for sources:

- Only public endpoints, no login, no bypassing of bot protection or rate limits.
- Use the shared client from `make_client` (honest User-Agent, ≥1 s between requests per host).
- No LinkedIn scraping.

## Pull requests

- Conventional commit messages (`feat:`, `fix:`, `docs:`, `test:`).
- Never include personal data (real CVs, profiles, job databases) or local assistant/AI tool files.
- Keep changes small. Prefer the standard library over new dependencies.
