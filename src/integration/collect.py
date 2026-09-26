"""Collect raw observations from the marketing/usage APIs.

Two kinds of pull:

- **Snapshot** (`collect`): today's values for every source — stars,
  forks, cumulative Docker/Hugging Face downloads, follower counts, and
  (with ``GITHUB_TOKEN``) the 14-day traffic window. Written to
  ``data/observations/{date}/``; ``run.yml`` carries ``data/`` from run
  to run in the Actions cache, so snapshot-only values accumulate
  there and traffic keeps its history past GitHub's 14 days.
- **History** (`collect_history`): the sources whose APIs carry their
  own history — npm, PyPI, Cloudflare Web Analytics, Search Console,
  YouTube Analytics, Buffer — pulled in full on every run, so backfill
  happens on the first run and closed months settle on the next.

Each history window starts on the first whole month its API still
retains: a month the window cuts into would assert a partial total.

Per-source failures skip that source and keep the rest (a dead API
should never cost the day's other snapshots). A source whose
credentials are absent is skipped quietly.
"""

from __future__ import annotations

import json
import os
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx

from integration.config import Config
from integration.sources import (
  BUFFER_CHANNELS,
  DOCKER_REPOS,
  GITHUB_ORG,
  GITHUB_REPOS,
  HUGGINGFACE_DATASETS,
  NPM_PACKAGES,
  PYPI_PACKAGE,
  SEARCH_CONSOLE_PROPERTIES,
  SITES,
  X_HANDLE,
  XBRLKIT_PYPI_PACKAGE,
  XBRLKIT_REPO,
)
from integration.transform import month_bounds

DATA_DIR = Path("data") / "observations"
_TIMEOUT = 30.0

# How far back each history API still holds data, in days.
_NPM_RETENTION = 540
_PYPI_RETENTION = 180
_CLOUDFLARE_RETENTION = 180
_SEARCH_CONSOLE_RETENTION = 480
_YOUTUBE_START = date(2020, 1, 1)


class SkipSource(Exception):
  """The source's credentials are not configured."""


def _today() -> date:
  return datetime.now(UTC).date()


def window_start(retention_days: int, today: date | None = None) -> date:
  """First day of the earliest month wholly inside the retention window."""
  earliest = (today or _today()) - timedelta(days=retention_days)
  if earliest.day == 1:
    return earliest
  if earliest.month == 12:
    return date(earliest.year + 1, 1, 1)
  return date(earliest.year, earliest.month + 1, 1)


def _months_since(start: date) -> list[str]:
  """Calendar months from ``start``'s month through this one, oldest first."""
  today = _today()
  first = start.year * 12 + start.month - 1
  last = today.year * 12 + today.month - 1
  return [f"{i // 12:04d}-{i % 12 + 1:02d}" for i in range(first, last + 1)]


def _env(name: str) -> str:
  value = os.environ.get(name, "")
  if not value:
    raise SkipSource(name)
  return value


def _get_json(url: str, headers: dict | None = None, params: dict | None = None) -> Any:
  response = httpx.get(url, headers=headers or {}, params=params, timeout=_TIMEOUT)
  response.raise_for_status()
  return response.json()


def _post_json(url: str, body: dict, headers: dict | None = None) -> Any:
  response = httpx.post(url, json=body, headers=headers or {}, timeout=_TIMEOUT)
  response.raise_for_status()
  return response.json()


def google_access_token(service: str) -> str:
  """Exchange a refresh token for an access token.

  ``{service}_CLIENT_ID`` / ``_CLIENT_SECRET`` / ``_REFRESH_TOKEN``
  win when all three are set; otherwise the shared ``GOOGLE_*`` grant.
  """
  for prefix in (service, "GOOGLE"):
    client_id = os.environ.get(f"{prefix}_CLIENT_ID")
    client_secret = os.environ.get(f"{prefix}_CLIENT_SECRET")
    refresh_token = os.environ.get(f"{prefix}_REFRESH_TOKEN")
    if client_id and client_secret and refresh_token:
      response = httpx.post(
        "https://oauth2.googleapis.com/token",
        data={
          "client_id": client_id,
          "client_secret": client_secret,
          "refresh_token": refresh_token,
          "grant_type": "refresh_token",
        },
        timeout=_TIMEOUT,
      )
      response.raise_for_status()
      return response.json()["access_token"]
  raise SkipSource(f"{service}_* / GOOGLE_*")


# ── Snapshots ─────────────────────────────────────────────────────────


def collect_github(token: str | None = None) -> dict:
  """Stars/forks/watchers per repo; traffic (views/clones) with a PAT."""
  headers = {"Authorization": f"Bearer {token}"} if token else {}
  repos: dict[str, Any] = {}
  for name in [*GITHUB_REPOS, XBRLKIT_REPO]:
    data = _get_json(f"https://api.github.com/repos/{GITHUB_ORG}/{name}", headers)
    entry = {
      "stars": data["stargazers_count"],
      "forks": data["forks_count"],
      "watchers": data["subscribers_count"],
    }
    if token:
      base = f"https://api.github.com/repos/{GITHUB_ORG}/{name}/traffic"
      entry["traffic_views"] = _get_json(f"{base}/views", headers)
      entry["traffic_clones"] = _get_json(f"{base}/clones", headers)
    repos[name] = entry
  return repos


def collect_npm_yesterday() -> dict:
  """Yesterday's per-package downloads (the daily snapshot grain)."""
  day = (_today() - timedelta(days=1)).isoformat()
  return {
    package: _get_json(
      f"https://api.npmjs.org/downloads/point/{day}:{day}/{package}"
    ).get("downloads", 0)
    for package in NPM_PACKAGES
  }


def collect_dockerhub() -> dict:
  """Cumulative pull counts — snapshot-only; the rate series lives in
  the accumulated daily files."""
  return {
    repo: _get_json(f"https://hub.docker.com/v2/repositories/{repo}/")["pull_count"]
    for repo in DOCKER_REPOS
  }


def collect_huggingface() -> dict:
  """All-time dataset downloads (cumulative, like Docker pulls)."""
  return {
    dataset: _get_json(
      f"https://huggingface.co/api/datasets/{dataset}",
      params={"expand[]": "downloadsAllTime"},
    )["downloadsAllTime"]
    for dataset in HUGGINGFACE_DATASETS
  }


def collect_youtube_channel() -> dict:
  token = google_access_token("YOUTUBE")
  data = _get_json(
    "https://www.googleapis.com/youtube/v3/channels",
    headers={"Authorization": f"Bearer {token}"},
    params={"part": "statistics", "mine": "true"},
  )
  stats = data["items"][0]["statistics"]
  return {
    "subscribers": int(stats["subscriberCount"]),
    "views": int(stats["viewCount"]),
    "videos": int(stats["videoCount"]),
  }


def collect_x() -> dict:
  data = _get_json(
    f"https://api.x.com/2/users/by/username/{X_HANDLE}",
    headers={"Authorization": f"Bearer {_env('X_BEARER_TOKEN')}"},
    params={"user.fields": "public_metrics"},
  )
  return data["data"]["public_metrics"]


def collect(config: Config) -> dict[str, Any]:
  """Daily snapshot across all sources; raw JSON lands in data/."""
  out_dir = DATA_DIR / _today().isoformat()
  out_dir.mkdir(parents=True, exist_ok=True)

  collectors = {
    "github": lambda: collect_github(os.environ.get("GITHUB_TOKEN") or None),
    "npm": collect_npm_yesterday,
    "dockerhub": collect_dockerhub,
    "huggingface": collect_huggingface,
    "youtube": collect_youtube_channel,
    "x": collect_x,
  }
  snapshot: dict[str, Any] = {"collected_at": datetime.now(UTC).isoformat()}
  for source, fn in collectors.items():
    try:
      snapshot[source] = fn()
    except SkipSource as missing:
      print(f"  skip: {source} (no {missing})")
      continue
    except Exception as exc:
      print(f"  WARN: {source} collection failed, skipping: {exc}")
      continue
    (out_dir / f"{source}.json").write_text(json.dumps(snapshot[source], indent=2))
  return snapshot


# ── History ───────────────────────────────────────────────────────────


def history_npm() -> dict:
  start = window_start(_NPM_RETENTION).isoformat()
  end = _today().isoformat()
  return {
    package: _get_json(
      f"https://api.npmjs.org/downloads/range/{start}:{end}/{package}"
    ).get("downloads", [])
    for package in NPM_PACKAGES
  }


def history_pypi() -> dict:
  start = window_start(_PYPI_RETENTION).isoformat()
  history = {}
  for package in (PYPI_PACKAGE, XBRLKIT_PYPI_PACKAGE):
    data = _get_json(f"https://pypistats.org/api/packages/{package}/overall")
    history[package] = [
      row
      for row in data.get("data", [])
      if row.get("category") == "without_mirrors" and row["date"] >= start
    ]
  return history


def history_cloudflare() -> dict:
  """Daily page views and visits per tracked site.

  Web Analytics samples at ingestion (``sampleInterval`` 10 on this
  account), so the counts are estimates scaled from the sample — the
  same numbers the dashboard shows.
  """
  account = _env("CLOUDFLARE_ACCOUNT_ID")
  headers = {"Authorization": f"Bearer {_env('CLOUDFLARE_API_TOKEN')}"}
  sites = _get_json(
    f"https://api.cloudflare.com/client/v4/accounts/{account}/rum/site_info/list",
    headers,
  )["result"]
  host_by_tag = {
    site["site_tag"]: site["host"] for site in sites if site.get("host") in SITES
  }
  query = """
    query ($account: String!, $start: Date!, $end: Date!) {
      viewer { accounts(filter: {accountTag: $account}) {
        rumPageloadEventsAdaptiveGroups(
          limit: 10000, filter: {date_geq: $start, date_leq: $end}
        ) { count sum { visits } dimensions { date siteTag } }
      } }
    }
  """
  # One query per month: the API caps a query's range well inside its
  # retention window.
  history: dict[str, list[dict]] = {host: [] for host in host_by_tag.values()}
  today = _today()
  for month in _months_since(window_start(_CLOUDFLARE_RETENTION)):
    start, end = month_bounds(month)
    data = _post_json(
      "https://api.cloudflare.com/client/v4/graphql",
      {
        "query": query,
        "variables": {
          "account": account,
          "start": start.isoformat(),
          "end": min(end, today).isoformat(),
        },
      },
      headers,
    )
    if data.get("errors"):
      raise RuntimeError(data["errors"][0].get("message"))
    groups = data["data"]["viewer"]["accounts"][0]["rumPageloadEventsAdaptiveGroups"]
    for group in groups:
      host = host_by_tag.get(group["dimensions"]["siteTag"])
      if host:
        history[host].append(
          {
            "date": group["dimensions"]["date"],
            "pageviews": group["count"],
            "visits": group["sum"]["visits"],
          }
        )
  return history


def history_search_console() -> dict:
  """Daily Google clicks and impressions per property."""
  headers = {"Authorization": f"Bearer {google_access_token('GSC')}"}
  body = {
    "startDate": window_start(_SEARCH_CONSOLE_RETENTION).isoformat(),
    "endDate": _today().isoformat(),
    "dimensions": ["date"],
    "rowLimit": 25000,
  }
  history = {}
  for prop in SEARCH_CONSOLE_PROPERTIES:
    encoded = prop.replace(":", "%3A")
    data = _post_json(
      f"https://www.googleapis.com/webmasters/v3/sites/{encoded}/searchAnalytics/query",
      body,
      headers,
    )
    history[prop] = [
      {
        "date": row["keys"][0],
        "clicks": row["clicks"],
        "impressions": row["impressions"],
      }
      for row in data.get("rows", [])
    ]
  return history


def history_youtube() -> list[dict]:
  """Daily views and watch minutes for the whole channel history."""
  data = _get_json(
    "https://youtubeanalytics.googleapis.com/v2/reports",
    headers={"Authorization": f"Bearer {google_access_token('YOUTUBE')}"},
    params={
      "ids": "channel==MINE",
      "startDate": _YOUTUBE_START.isoformat(),
      "endDate": _today().isoformat(),
      "metrics": "views,estimatedMinutesWatched",
      "dimensions": "day",
    },
  )
  return [
    {"date": day, "views": views, "minutes": minutes}
    for day, views, minutes in data.get("rows") or []
  ]


def _buffer(query: str) -> dict:
  data = _post_json(
    "https://api.buffer.com",
    {"query": query},
    {"Authorization": f"Bearer {_env('BUFFER_API_KEY')}"},
  )
  if data.get("errors"):
    raise RuntimeError(data["errors"][0].get("message"))
  return data["data"]


def history_buffer() -> dict:
  """Impressions of the posts published each month, per channel.

  Buffer attributes a post's lifetime impressions to the month it was
  published, so recent months keep growing and settle over the
  following weeks — every run re-reads the whole window.
  """
  _env("BUFFER_API_KEY")
  today = _today()
  buffer_start = date(today.year - 1, today.month, 1)
  organizations = _buffer("{ account { organizations { id } } }")["account"][
    "organizations"
  ]
  history: dict[str, dict[str, dict]] = {}
  for org in organizations:
    channels = _buffer(
      f'{{ channels(input: {{organizationId: "{org["id"]}"}}) {{ id service }} }}'
    )["channels"]
    for channel in channels:
      concept = BUFFER_CHANNELS.get(channel["service"])
      if concept is None:
        continue
      for month in _months_since(buffer_start):
        start, end = month_bounds(month)
        metrics = _buffer(
          f"""{{ aggregatedPostMetrics(input: {{
              organizationId: "{org["id"]}", channelIds: ["{channel["id"]}"],
              startDateTime: "{start.isoformat()}T00:00:00Z",
              endDateTime: "{end.isoformat()}T23:59:59Z"
            }}) {{ metrics {{ type value }} }} }}"""
        )["aggregatedPostMetrics"]["metrics"]
        values = {metric["type"]: metric["value"] for metric in metrics}
        bucket = history.setdefault(concept, {}).setdefault(
          month, {"posts": 0, "impressions": 0}
        )
        bucket["posts"] += int(values.get("postCount", 0))
        bucket["impressions"] += int(values.get("impressions", 0))
  return history


def load_traffic(data_dir: Path = DATA_DIR) -> dict[str, Any]:
  """Daily GitHub traffic per repo, merged across every stored snapshot.

  Each snapshot holds a 14-day window; the latest file's value for a
  day wins (a day's count settles after it ends). ``covered_from`` is
  the first day the stored snapshots reach back to.
  """
  repos: dict[str, dict[str, dict[str, int]]] = {}
  covered_from: str | None = None
  if not data_dir.is_dir():
    return {"repos": repos, "covered_from": None}
  for day_dir in sorted(p for p in data_dir.iterdir() if p.is_dir()):
    path = day_dir / "github.json"
    if not path.is_file():
      continue
    for repo, entry in json.loads(path.read_text()).items():
      for kind in ("views", "clones"):
        block = entry.get(f"traffic_{kind}")
        if not block:
          continue
        if covered_from is None:
          collected = date.fromisoformat(day_dir.name)
          covered_from = (collected - timedelta(days=13)).isoformat()
        series = repos.setdefault(repo, {}).setdefault(kind, {})
        for row in block.get(kind, []):
          series[row["timestamp"][:10]] = int(row["count"])
  return {"repos": repos, "covered_from": covered_from}


def collect_history() -> dict[str, Any]:
  """Full available history for the sources that carry their own."""
  pulls = {
    "npm": history_npm,
    "pypi": history_pypi,
    "cloudflare": history_cloudflare,
    "search_console": history_search_console,
    "youtube": history_youtube,
    "buffer": history_buffer,
  }
  history: dict[str, Any] = {}
  for source, fn in pulls.items():
    try:
      history[source] = fn()
    except SkipSource as missing:
      print(f"  skip: {source} history (no {missing})")
    except Exception as exc:
      print(f"  WARN: {source} history failed, skipping: {exc}")
  history["github_traffic"] = load_traffic()
  return history
