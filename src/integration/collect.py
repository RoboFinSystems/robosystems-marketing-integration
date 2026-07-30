"""Collect raw observations from the public marketing/usage APIs.

Two kinds of pull:

- **Snapshot** (`collect`): today's values for every source — stars,
  forks, cumulative Docker pulls, and (with ``GITHUB_TOKEN``) the
  14-day traffic window. Written to ``data/observations/{date}/`` so
  the raw history accumulates locally run over run; snapshot-only
  values (stars, pulls) have no history API, so these files ARE the
  series.
- **History** (`collect_history`): the sources whose APIs carry their
  own history — npm (range API, 18 months) and PyPI (pypistats,
  ~180 days) — pulled in full for backfill.

Per-source failures skip that source and keep the rest (a dead API
should never cost the day's other snapshots).
"""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx

from integration.config import Config
from integration.sources import (
  DOCKER_REPOS,
  GITHUB_ORG,
  GITHUB_REPOS,
  NPM_PACKAGES,
  PYPI_PACKAGES,
)

DATA_DIR = Path("data") / "observations"
_TIMEOUT = 30.0


def _get_json(url: str, headers: dict | None = None) -> Any:
  response = httpx.get(url, headers=headers or {}, timeout=_TIMEOUT)
  response.raise_for_status()
  return response.json()


def collect_github(token: str | None = None) -> dict:
  """Stars/forks/watchers per repo; traffic (views/clones) with a PAT."""
  headers = {"Authorization": f"Bearer {token}"} if token else {}
  repos: dict[str, Any] = {}
  for name in GITHUB_REPOS:
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
  day = (datetime.now(UTC).date() - timedelta(days=1)).isoformat()
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


def collect(config: Config) -> dict[str, Any]:
  """Daily snapshot across all sources; raw JSON lands in data/."""
  today = datetime.now(UTC).date().isoformat()
  out_dir = DATA_DIR / today
  out_dir.mkdir(parents=True, exist_ok=True)

  collectors = {
    "github": lambda: collect_github(os.environ.get("GITHUB_TOKEN")),
    "npm": collect_npm_yesterday,
    "dockerhub": collect_dockerhub,
  }
  snapshot: dict[str, Any] = {"collected_at": datetime.now(UTC).isoformat()}
  for source, fn in collectors.items():
    try:
      snapshot[source] = fn()
    except Exception as exc:
      print(f"  WARN: {source} collection failed, skipping: {exc}")
      continue
    (out_dir / f"{source}.json").write_text(json.dumps(snapshot[source], indent=2))
  return snapshot


def collect_history() -> dict[str, Any]:
  """Full available history for the sources that carry their own."""
  today = datetime.now(UTC).date()
  start = (today - timedelta(days=540)).isoformat()  # npm caps at 18 months
  history: dict[str, Any] = {"npm": {}, "pypi": {}}
  for package in NPM_PACKAGES:
    try:
      data = _get_json(
        f"https://api.npmjs.org/downloads/range/{start}:{today.isoformat()}/{package}"
      )
      history["npm"][package] = data.get("downloads", [])
    except Exception as exc:
      print(f"  WARN: npm history for {package} failed: {exc}")
  for package in PYPI_PACKAGES:
    try:
      data = _get_json(f"https://pypistats.org/api/packages/{package}/overall")
      history["pypi"][package] = [
        row for row in data.get("data", []) if row.get("category") == "without_mirrors"
      ]
    except Exception as exc:
      print(f"  WARN: pypi history for {package} failed: {exc}")
  return history
