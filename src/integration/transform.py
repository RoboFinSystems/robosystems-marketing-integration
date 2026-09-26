"""Roll raw observations up to monthly assertion sets.

Daily raw stays in ``data/``; the graph gets months (the reporting
rhythm). Two shapes:

- **Duration concepts** (downloads, views, impressions): summed per
  calendar month from the sources' own history APIs — so backfill
  produces real historical months on day one. The current month is
  month-to-date and re-asserted on every run; closed months settle on
  the run after they close.
- **Instant concepts** (stars, followers, cumulative pulls): no history
  API — only the current month can be asserted, valued at today's
  snapshot. Re-running before month end re-asserts with a fresher
  value (replace-per-period makes the last run before close win).
"""

from __future__ import annotations

from calendar import monthrange
from datetime import UTC, date, datetime
from typing import Any

from integration.sources import (
  PYPI_PACKAGE,
  SITES,
  XBRLKIT_PYPI_PACKAGE,
  XBRLKIT_REPO,
)

Months = dict[str, dict[str, float]]


def month_bounds(month: str) -> tuple[date, date]:
  """``"2026-07"`` → (first day, last day)."""
  year, mon = int(month[:4]), int(month[5:7])
  return date(year, mon, 1), date(year, mon, monthrange(year, mon)[1])


def _add(months: Months, concept: str, month: str, value: float) -> None:
  bucket = months.setdefault(month, {})
  bucket[concept] = bucket.get(concept, 0.0) + float(value)


def _add_daily(
  months: Months, concept: str, rows: list[dict], day_key: str, value_key: str
) -> None:
  """Sum per-day rows into ``concept`` per month."""
  for row in rows:
    _add(months, concept, str(row[day_key])[:7], row[value_key])


def monthly_history(history: dict[str, Any]) -> Months:
  """History → ``{month: {concept: value}}`` for every duration concept."""
  months: Months = {}

  for rows in history.get("npm", {}).values():
    _add_daily(months, "rsx:NpmDownloads", rows, "day", "downloads")

  pypi = history.get("pypi", {})
  _add_daily(
    months, "rsx:PypiDownloads", pypi.get(PYPI_PACKAGE, []), "date", "downloads"
  )
  _add_daily(
    months,
    "rsx:XbrlkitPypiDownloads",
    pypi.get(XBRLKIT_PYPI_PACKAGE, []),
    "date",
    "downloads",
  )

  for host, rows in history.get("cloudflare", {}).items():
    stem = SITES.get(host)
    if stem:
      _add_daily(months, f"rsx:{stem}SitePageViews", rows, "date", "pageviews")
      _add_daily(months, f"rsx:{stem}SiteVisits", rows, "date", "visits")

  for rows in history.get("search_console", {}).values():
    _add_daily(months, "rsx:SearchImpressions", rows, "date", "impressions")
    _add_daily(months, "rsx:SearchClicks", rows, "date", "clicks")

  youtube = history.get("youtube", [])
  _add_daily(months, "rsx:YoutubeViews", youtube, "date", "views")
  _add_daily(months, "rsx:YoutubeWatchMinutes", youtube, "date", "minutes")

  for concept, by_month in history.get("buffer", {}).items():
    posted = sorted(month for month, row in by_month.items() if row["posts"] > 0)
    if not posted:
      continue
    for month, row in by_month.items():
      if month >= posted[0]:
        _add(months, concept, month, row["impressions"])

  _add_traffic(months, history.get("github_traffic") or {})
  return _drop_leading_zeros(months)


def _drop_leading_zeros(months: Months) -> Months:
  """Drop each concept's all-zero months before its first real value.

  History APIs report zeros for the days before a package, site or
  channel existed; asserting them would claim a measurement of
  something that was not there yet.
  """
  first_seen: dict[str, str] = {}
  for month in sorted(months):
    for concept, value in months[month].items():
      if value and concept not in first_seen:
        first_seen[concept] = month
  trimmed: Months = {}
  for month, observations in months.items():
    kept = {
      concept: value
      for concept, value in observations.items()
      if concept in first_seen and month >= first_seen[concept]
    }
    if kept:
      trimmed[month] = kept
  return trimmed


def _add_traffic(months: Months, traffic: dict[str, Any]) -> None:
  """Sum stored daily traffic per month, skipping months the stored
  snapshots do not reach back to the start of (a partial total)."""
  covered_from = traffic.get("covered_from")
  if not covered_from:
    return
  targets = {
    "views": ("rsx:GithubViews", "rsx:XbrlkitGithubViews"),
    "clones": ("rsx:GithubClones", None),
  }
  for repo, kinds in traffic.get("repos", {}).items():
    for kind, series in kinds.items():
      robosystems_concept, xbrlkit_concept = targets[kind]
      concept = xbrlkit_concept if repo == XBRLKIT_REPO else robosystems_concept
      if concept is None:
        continue
      for day, count in series.items():
        month = day[:7]
        if month_bounds(month)[0].isoformat() >= covered_from:
          _add(months, concept, month, count)


def snapshot_instants(snapshot: dict[str, Any]) -> dict[str, float]:
  """Today's snapshot → the instant-concept observations."""
  observations: dict[str, float] = {}
  github = snapshot.get("github")
  if github:
    robosystems = [row for repo, row in github.items() if repo != XBRLKIT_REPO]
    observations["rsx:GithubStars"] = sum(r["stars"] for r in robosystems)
    observations["rsx:GithubForks"] = sum(r["forks"] for r in robosystems)
    if XBRLKIT_REPO in github:
      observations["rsx:XbrlkitGithubStars"] = github[XBRLKIT_REPO]["stars"]
  docker = snapshot.get("dockerhub")
  if docker:
    observations["rsx:DockerPulls"] = sum(docker.values())
  huggingface = snapshot.get("huggingface")
  if huggingface:
    observations["rsx:HuggingFaceDownloads"] = sum(huggingface.values())
  youtube = snapshot.get("youtube")
  if youtube:
    observations["rsx:YoutubeSubscribers"] = youtube["subscribers"]
  x = snapshot.get("x")
  if x:
    observations["rsx:XFollowers"] = x["followers_count"]
  return {concept: float(value) for concept, value in observations.items()}


def transform(snapshot: dict[str, Any], history: dict[str, Any]) -> Months:
  """Build the full per-month observation sets to assert.

  Every month with history gets its duration concepts; the current
  month additionally gets the instant concepts at today's values.
  """
  months = monthly_history(history)
  current = datetime.now(UTC).date().isoformat()[:7]
  months.setdefault(current, {}).update(snapshot_instants(snapshot))
  return months
