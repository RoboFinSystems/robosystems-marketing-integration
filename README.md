# RoboSystems Marketing Integration

RFS's own marketing and usage metrics, collected from public APIs and asserted as an observed metric series on a [RoboSystems](https://github.com/RoboFinSystems/robosystems) graph — where they render as a time-series Information Block next to the financials.

This is a real integration built from [`robosystems-integration-template`](https://github.com/RoboFinSystems/robosystems-integration-template) (lane 2 — semantic facts), and doubles as the living reference for the pattern: it lives outside the platform, holds its own source access, and speaks only the public API with an API key.

## What it tracks

| Series | Kind | Source | Credentials |
|---|---|---|---|
| GitHub stars / forks — RoboSystems repos; stars — xbrlkit | instant | GitHub REST | none |
| GitHub repo views / clones — RoboSystems; views — xbrlkit | monthly | GitHub traffic API | `GITHUB_TOKEN` (PAT, push access) |
| npm downloads (`@robosystems/mcp`, `@robosystems/core`) | monthly | npm downloads API | none |
| PyPI downloads — `robosystems-client`; `xbrlkit` | monthly | pypistats | none |
| Docker pulls (`robofinsystems/robosystems`) | instant (cumulative) | Docker Hub | none |
| Hugging Face dataset downloads | instant (cumulative) | Hugging Face Hub API | none |
| Site page views / visits — robosystems.ai, roboledger.ai, roboinvestor.ai, xbrlkit.com, harbinger.finance | monthly | Cloudflare Web Analytics | `CLOUDFLARE_ACCOUNT_ID`, `CLOUDFLARE_API_TOKEN` |
| Google search impressions / clicks (the five sites) | monthly | Search Console | `GOOGLE_*` |
| YouTube views / watch minutes; subscribers | monthly; instant | YouTube Analytics + Data API | `GOOGLE_*` |
| X followers (@RoboFinSystems) | instant | X API v2 | `X_BEARER_TOKEN` |
| LinkedIn / X post impressions | monthly (by publish month) | Buffer | `BUFFER_API_KEY` |

Every credentialed source is optional — without its variables it is skipped and its series gets no value that month. `GOOGLE_*` is one read-only grant for Search Console and YouTube; mint it with `just google-auth path/to/client_secret.json`. The catalog and the vocabulary live in `src/integration/sources.py`.

Two sources are perishable: GitHub keeps **14 days** of traffic and Cloudflare Web Analytics about **six months**. Traffic history exists only because `data/` persists run to run (the Actions cache in `run.yml`). Cloudflare's counts are estimates from its ingestion sample.

**The vocabulary is authored once.** `ensure_structure` never extends an existing structure: a concept added to `CONCEPTS` after the first run is reported as missing and left unasserted until it is added to the structure.

## How it works

Each run (daily on the `run.yml` schedule, or `just run`):

1. **Snapshot** every source into `data/observations/{date}/` — raw history accumulates run over run; for snapshot-only values (stars, pulls) these files *are* the series.
2. **Pull history** from the sources that carry their own (npm: 18 months; PyPI, Cloudflare: ~6 months; Search Console: 16 months; Buffer: 12 months; YouTube: full) — each window starts on the first whole month still retained, and months before a series' first non-zero value are dropped.
3. **Roll up to months** and assert each one via the `assert-metrics` operation — historical months backfill on the first run; the current month re-asserts with fresher values until it closes (replace-per-period makes re-runs idempotent).

The vocabulary — a `block_type='metric'` structure with no Derive rules — is authored once via `create-taxonomy-block` and resolved by name on every run after. The platform renders the series everywhere (Block Explorer, charts, fact grids, GraphQL, MCP) with no further work here.

## Running

```bash
just venv          # environment + dependencies + git hooks
# fill in .env: ROBOSYSTEMS_API_KEY, ROBOSYSTEMS_GRAPH_ID
just run
```

On a schedule: set `secrets.ROBOSYSTEMS_API_KEY` plus `vars.ROBOSYSTEMS_GRAPH_ID` / `vars.INTEGRATION_SOURCE_NAME` in the repo's Actions settings, and whichever source credentials you want — the list is in `run.yml`'s header. The traffic PAT goes in `secrets.GH_TRAFFIC_TOKEN` (GitHub reserves the `GITHUB_` prefix). `run.yml` does the rest. `just test-all` is the CI gate (tests + format + lint + typecheck).

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

MIT © 2026 RFS LLC

