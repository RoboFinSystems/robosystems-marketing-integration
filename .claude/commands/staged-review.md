---
description: Review the staged diff against this integration's lane, idempotency, and credential rules.
---

Review all staged changes (`git diff --cached`) with focus on the contexts below. Read the diff first — if nothing is staged, say so rather than reviewing the working tree.

This is the **RoboSystems marketing integration** — a real Lane 2 (semantic facts) integration built from `robosystems-integration-template`. It collects public marketing/usage metrics (GitHub, npm, PyPI, Docker Hub) and asserts them as an observed metric series. It speaks to the platform only through its public API with an API key, and runs daily on the `run.yml` schedule. Everything Python runs through `uv run`.

## The lane

An integration picks one or more of three lanes, and the lane determines what correctness means:

- **Lane 1 — Ledger** (`emit/events.py`): business events into the general ledger. The platform enforces double-entry balance, capture-then-approve, the closed-period gate, and `(source, external_id)` idempotency. Review any change here against those: is `external_id` stable across runs, and genuinely unique per event? An unstable one duplicates every run.
- **Lane 2 — Semantic facts** (`emit/metrics.py`): **this integration's lane.** A custom vocabulary plus observed metric series, replaced per period — so re-running is safe *if* the period key is right. Check it. The vocabulary and tracked-asset catalog live in `src/integration/sources.py`; adding a concept there changes what renders on the graph.
- **Lane 3 — Raw graph** (`emit/graph.py`): files → staging → materialize.

A change that mixes lanes, or that bypasses an emitter to call the API directly, is worth flagging — the emitters exist so the platform's guarantees apply.

## Idempotency

These run on a schedule (`run.yml`), so **every change is a change to something that will execute unattended, repeatedly**:

- Does running twice produce the same result? Lane 1 relies on `(source, external_id)`; Lane 2 on per-period replacement.
- Does a partial failure leave the source and platform consistent, or half-emitted?
- Is the collect step bounded — pagination, time windows, retry limits — rather than assuming the source is small? Several sources are rate-limited, and GitHub traffic needs `GITHUB_TOKEN`.
- **GitHub traffic data is perishable**: the API retains only 14 days, so history exists solely because this integration keeps collecting it. A change that skips or breaks a run loses data permanently — there is no backfill. Weight that accordingly.

## Credentials and configuration

- The API key lives in `.env` (locally) and repository secrets (in Actions). **Never staged, never logged, never in an error message.** An API key in a traceback is a real leak.
- New configuration should flow through `config.py` and `.env.example`, so a derived repo knows the knob exists.
- Is the graph id configurable rather than hardcoded? A hardcoded graph is how an integration writes into the wrong customer's data.

## Structure

- `collect.py` extracts, `transform.py` shapes, `emit/` sends, `client.py` is the API boundary, `main.py` wires them. Logic that reaches across those seams — a collector that emits, a transform that fetches — makes the pipeline untestable.
- Keep `client.py` the single place that talks HTTP; that's what makes stubbing in tests possible.

## Testing

- Do tests stub at `client.py` rather than calling the live API? A test that emits for real writes real data.
- Is idempotency covered — the second run, not just the first?

## Output

1. **Issues**: Problems that should be fixed before commit
2. **Suggestions**: Improvements that aren't blocking
3. **Questions**: Anything unclear

Anchor findings to `file:line`. Call out anything affecting idempotency or credentials explicitly, even if the rest is clean.
