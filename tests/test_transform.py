"""Rollup logic — pure functions over fixture history/snapshot data."""

from __future__ import annotations

from datetime import UTC, datetime

from integration.transform import (
  month_bounds,
  monthly_downloads,
  snapshot_instants,
  transform,
)

HISTORY = {
  "npm": {
    "@robosystems/mcp": [
      {"day": "2026-06-29", "downloads": 10},
      {"day": "2026-06-30", "downloads": 5},
      {"day": "2026-07-01", "downloads": 7},
    ],
    "@robosystems/core": [
      {"day": "2026-06-30", "downloads": 100},
      {"day": "2026-07-01", "downloads": 50},
    ],
  },
  "pypi": {
    "robosystems-client": [
      {"date": "2026-06-15", "downloads": 40},
      {"date": "2026-07-02", "downloads": 60},
    ],
  },
}

SNAPSHOT = {
  "collected_at": "2026-07-30T12:00:00+00:00",
  "github": {
    "robosystems": {"stars": 19, "forks": 6, "watchers": 2},
    "robosystems-mcp-client": {"stars": 3, "forks": 1, "watchers": 1},
  },
  "dockerhub": {"robofinsystems/robosystems": 38232},
}


class TestMonthBounds:
  def test_regular_and_leap_months(self) -> None:
    start, end = month_bounds("2026-07")
    assert (start.isoformat(), end.isoformat()) == ("2026-07-01", "2026-07-31")
    start, end = month_bounds("2028-02")
    assert end.isoformat() == "2028-02-29"


class TestMonthlyDownloads:
  def test_sums_across_packages_per_month(self) -> None:
    months = monthly_downloads(HISTORY)
    assert months["2026-06"]["rsx:NpmDownloads"] == 115
    assert months["2026-07"]["rsx:NpmDownloads"] == 57
    assert months["2026-06"]["rsx:PypiDownloads"] == 40
    assert months["2026-07"]["rsx:PypiDownloads"] == 60


class TestSnapshotInstants:
  def test_sums_repos_and_registries(self) -> None:
    observations = snapshot_instants(SNAPSHOT)
    assert observations["rsx:GithubStars"] == 22
    assert observations["rsx:GithubForks"] == 7
    assert observations["rsx:DockerPulls"] == 38232

  def test_missing_sources_omit_concepts(self) -> None:
    assert snapshot_instants({"collected_at": "x"}) == {}


class TestTransform:
  def test_current_month_gets_instants_history_months_do_not(self) -> None:
    months = transform(SNAPSHOT, HISTORY)
    current = datetime.now(UTC).date().isoformat()[:7]
    assert "rsx:GithubStars" in months[current]
    for month, observations in months.items():
      if month != current:
        assert "rsx:GithubStars" not in observations
    assert months["2026-06"]["rsx:NpmDownloads"] == 115
