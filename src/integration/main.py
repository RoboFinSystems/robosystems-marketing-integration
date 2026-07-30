"""Entry point: snapshot → rollup → assert.

Run locally with ``uv run python -m integration.main`` (or on the
``run.yml`` schedule). Each run:

1. snapshots every source into ``data/observations/{today}/``
2. pulls the download-history APIs (npm/PyPI carry their own history)
3. rolls everything up to months and asserts each one — historical
   months backfill on the first run; the current month refreshes on
   every run until it closes (replace-per-period)
"""

from __future__ import annotations

from integration.client import IntegrationClient
from integration.collect import collect, collect_history
from integration.config import load_config
from integration.emit.metrics import assert_metrics
from integration.transform import month_bounds, transform
from integration.vocabulary import ensure_structure


def run() -> None:
  config = load_config()
  client = IntegrationClient(config)
  try:
    structure_id = ensure_structure(client)
    print(f"structure: {structure_id}")

    snapshot = collect(config)
    history = collect_history()
    months = transform(snapshot, history)

    for month in sorted(months):
      observations = months[month]
      if not observations:
        continue
      period_start, period_end = month_bounds(month)
      assert_metrics(
        client,
        structure_id=structure_id,
        period_start=period_start,
        period_end=period_end,
        observations=observations,
        basis_note=f"collected {snapshot.get('collected_at', '')[:10]}",
      )
      print(f"asserted {month}: {sorted(observations)}")
    print(f"done — {len(months)} month(s)")
  finally:
    client.close()


if __name__ == "__main__":
  run()
