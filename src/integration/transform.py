"""Roll raw observations up to monthly assertion sets.

Daily raw stays in ``data/``; the graph gets months (the reporting
rhythm). Two shapes:

- **Duration concepts** (downloads): summed per calendar month from the
  sources' own history APIs — so backfill produces real historical
  months on day one.
- **Instant concepts** (stars, forks, cumulative pulls): no history
  API — only the current month can be asserted, valued at today's
  snapshot. Re-running before month end re-asserts with a fresher
  value (replace-per-period makes the last run before close win).
"""

from __future__ import annotations

from calendar import monthrange
from datetime import UTC, date, datetime
from typing import Any


def month_bounds(month: str) -> tuple[date, date]:
  """``"2026-07"`` → (first day, last day)."""
  year, mon = int(month[:4]), int(month[5:7])
  return date(year, mon, 1), date(year, mon, monthrange(year, mon)[1])


def _monthly_sums(
  daily_rows: list[dict], day_key: str, value_key: str
) -> dict[str, int]:
  """Sum per-day rows into ``{"YYYY-MM": total}``."""
  months: dict[str, int] = {}
  for row in daily_rows:
    month = str(row[day_key])[:7]
    months[month] = months.get(month, 0) + int(row[value_key])
  return months


def monthly_downloads(history: dict[str, Any]) -> dict[str, dict[str, float]]:
  """History → ``{month: {"rsx:NpmDownloads": n, "rsx:PypiDownloads": n}}``."""
  npm_months: dict[str, int] = {}
  for rows in history.get("npm", {}).values():
    for month, total in _monthly_sums(rows, "day", "downloads").items():
      npm_months[month] = npm_months.get(month, 0) + total
  pypi_months: dict[str, int] = {}
  for rows in history.get("pypi", {}).values():
    for month, total in _monthly_sums(rows, "date", "downloads").items():
      pypi_months[month] = pypi_months.get(month, 0) + total

  months: dict[str, dict[str, float]] = {}
  for month, total in npm_months.items():
    months.setdefault(month, {})["rsx:NpmDownloads"] = float(total)
  for month, total in pypi_months.items():
    months.setdefault(month, {})["rsx:PypiDownloads"] = float(total)
  return months


def snapshot_instants(snapshot: dict[str, Any]) -> dict[str, float]:
  """Today's snapshot → the instant-concept observations."""
  observations: dict[str, float] = {}
  github = snapshot.get("github")
  if github:
    observations["rsx:GithubStars"] = sum(r["stars"] for r in github.values())
    observations["rsx:GithubForks"] = sum(r["forks"] for r in github.values())
  docker = snapshot.get("dockerhub")
  if docker:
    observations["rsx:DockerPulls"] = sum(docker.values())
  return observations


def transform(
  snapshot: dict[str, Any], history: dict[str, Any]
) -> dict[str, dict[str, float]]:
  """Build the full per-month observation sets to assert.

  Every month with download history gets its duration concepts; the
  current month additionally gets the instant concepts at today's
  values.
  """
  months = {month: dict(obs) for month, obs in monthly_downloads(history).items()}
  current = datetime.now(UTC).date().isoformat()[:7]
  months.setdefault(current, {}).update(snapshot_instants(snapshot))
  return months
