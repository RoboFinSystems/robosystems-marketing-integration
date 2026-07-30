# RoboSystems Marketing Integration

RFS's own marketing and usage metrics, collected from public APIs and asserted as an observed metric series on a [RoboSystems](https://github.com/RoboFinSystems/robosystems) graph — where they render as a time-series Information Block next to the financials.

This is a real integration built from [`robosystems-integration-template`](https://github.com/RoboFinSystems/robosystems-integration-template) (lane 2 — semantic facts), and doubles as the living reference for the pattern: it lives outside the platform, holds its own source access, and speaks only the public API with an API key.

## What it tracks

| Concept | Kind | Source |
|---|---|---|
| `rsx:GithubStars` / `rsx:GithubForks` | instant | GitHub REST across the org's public repos |
| `rsx:NpmDownloads` | monthly | npm downloads API (`@robosystems/mcp`, `@robosystems/core`) |
| `rsx:PypiDownloads` | monthly | pypistats (`robosystems-client`, `robosystems-xbrl-holon`) |
| `rsx:DockerPulls` | instant (cumulative) | Docker Hub (`robofinsystems/robosystems`) |

With `GITHUB_TOKEN` set, GitHub **traffic** (views/clones) is also snapshotted — the perishable source: the API retains 14 days, so history exists only because this integration keeps collecting it. The tracked-asset catalog and the vocabulary live in `src/integration/sources.py`.

## How it works

Each run (daily on the `run.yml` schedule, or `just run`):

1. **Snapshot** every source into `data/observations/{date}/` — raw history accumulates run over run; for snapshot-only values (stars, pulls) these files *are* the series.
2. **Pull history** from the sources that carry their own (npm: 18 months; PyPI: ~180 days).
3. **Roll up to months** and assert each one via the `assert-metrics` operation — historical months backfill on the first run; the current month re-asserts with fresher values until it closes (replace-per-period makes re-runs idempotent).

The vocabulary — a `block_type='metric'` structure with no Derive rules — is authored once via `create-taxonomy-block` and resolved by name on every run after. The platform renders the series everywhere (Block Explorer, charts, fact grids, GraphQL, MCP) with no further work here.

## Running

```bash
just venv          # environment + dependencies + git hooks
# fill in .env: ROBOSYSTEMS_API_KEY, ROBOSYSTEMS_GRAPH_ID
just run
```

On a schedule: set `secrets.ROBOSYSTEMS_API_KEY` plus `vars.ROBOSYSTEMS_GRAPH_ID` / `vars.INTEGRATION_SOURCE_NAME` (and optionally `secrets.GITHUB_TOKEN` for traffic) in the repo's Actions settings — `run.yml` does the rest. `just test-all` is the CI gate (tests + format + lint + typecheck).

## License

MIT
