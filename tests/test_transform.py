"""Rollup logic — pure functions over fixture history/snapshot data."""

from __future__ import annotations

import json
from datetime import UTC, date, datetime
from pathlib import Path

from integration.collect import load_traffic, window_start
from integration.transform import (
  merge_asserted,
  month_bounds,
  monthly_history,
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
    "xbrlkit": [{"date": "2026-07-03", "downloads": 9}],
  },
  "cloudflare": {
    "robosystems.ai": [
      {"date": "2026-07-01", "pageviews": 30, "visits": 10},
      {"date": "2026-07-02", "pageviews": 20, "visits": 5},
    ],
    "supplyflowqc.com": [{"date": "2026-07-01", "pageviews": 99, "visits": 99}],
  },
  "search_console": {
    "sc-domain:robosystems.ai": [
      {"date": "2026-07-01", "clicks": 2, "impressions": 40}
    ],
    "sc-domain:xbrlkit.com": [{"date": "2026-07-05", "clicks": 1, "impressions": 10}],
  },
  "youtube": [
    {"date": "2026-07-01", "views": 12, "minutes": 30},
    {"date": "2026-07-09", "views": 8, "minutes": 5},
  ],
  "buffer": {
    "rsx:LinkedinImpressions": {
      "2026-05": {"posts": 0, "impressions": 0},
      "2026-06": {"posts": 3, "impressions": 400},
      "2026-07": {"posts": 0, "impressions": 0},
    }
  },
}

SNAPSHOT = {
  "collected_at": "2026-07-30T12:00:00+00:00",
  "github": {
    "robosystems": {"stars": 19, "forks": 6, "watchers": 2},
    "robosystems-typescript-client": {"stars": 3, "forks": 1, "watchers": 1},
    "xbrlkit": {"stars": 11, "forks": 2, "watchers": 1},
    "xbrlkit-viewer": {"stars": 2, "forks": 0, "watchers": 1},
  },
  "dockerhub": {"robofinsystems/robosystems": 38232},
  "huggingface": {"robosystems/sec-xbrl-knowledge-graphs": 169},
  "youtube": {"subscribers": 15, "views": 2830, "videos": 81},
  "x": {"followers_count": 33},
}


class TestMonthBounds:
  def test_regular_and_leap_months(self) -> None:
    start, end = month_bounds("2026-07")
    assert (start.isoformat(), end.isoformat()) == ("2026-07-01", "2026-07-31")
    start, end = month_bounds("2028-02")
    assert end.isoformat() == "2028-02-29"


class TestWindowStart:
  def test_rounds_up_to_the_first_whole_month(self) -> None:
    assert window_start(180, date(2026, 9, 26)) == date(2026, 4, 1)

  def test_keeps_a_window_that_starts_on_the_first(self) -> None:
    assert window_start(30, date(2026, 7, 31)) == date(2026, 7, 1)

  def test_rolls_over_the_year(self) -> None:
    assert window_start(10, date(2027, 1, 5)) == date(2027, 1, 1)


class TestMonthlyHistory:
  def test_downloads_sum_across_packages_and_split_xbrlkit(self) -> None:
    months = monthly_history(HISTORY)
    assert months["2026-06"]["rsx:NpmDownloads"] == 115
    assert months["2026-07"]["rsx:NpmDownloads"] == 57
    assert months["2026-06"]["rsx:PypiDownloads"] == 40
    assert months["2026-07"]["rsx:PypiDownloads"] == 60
    assert months["2026-07"]["rsx:XbrlkitPypiDownloads"] == 9

  def test_site_traffic_per_tracked_site_only(self) -> None:
    july = monthly_history(HISTORY)["2026-07"]
    assert july["rsx:RobosystemsSitePageViews"] == 50
    assert july["rsx:RobosystemsSiteVisits"] == 15
    assert not any("Supplyflow" in concept for concept in july)

  def test_search_sums_across_properties(self) -> None:
    july = monthly_history(HISTORY)["2026-07"]
    assert july["rsx:SearchImpressions"] == 50
    assert july["rsx:SearchClicks"] == 3

  def test_youtube_daily_rolls_up(self) -> None:
    july = monthly_history(HISTORY)["2026-07"]
    assert july["rsx:YoutubeViews"] == 20
    assert july["rsx:YoutubeWatchMinutes"] == 35

  def test_buffer_starts_at_the_first_month_with_posts(self) -> None:
    months = monthly_history(HISTORY)
    assert "rsx:LinkedinImpressions" not in months.get("2026-05", {})
    assert months["2026-06"]["rsx:LinkedinImpressions"] == 400
    assert months["2026-07"]["rsx:LinkedinImpressions"] == 0


def _write_snapshot(root: Path, day: str, github: dict) -> None:
  (root / day).mkdir(parents=True)
  (root / day / "github.json").write_text(json.dumps(github))


def _traffic(rows: list[tuple[str, int]]) -> dict:
  return {"views": [{"timestamp": f"{d}T00:00:00Z", "count": c} for d, c in rows]}


class TestTraffic:
  def test_latest_snapshot_wins_and_partial_first_month_is_dropped(
    self, tmp_path: Path
  ) -> None:
    _write_snapshot(
      tmp_path,
      "2026-09-20",
      {"robosystems": {"traffic_views": _traffic([("2026-09-19", 4)])}},
    )
    _write_snapshot(
      tmp_path,
      "2026-10-05",
      {
        "robosystems": {
          "traffic_views": _traffic([("2026-09-19", 5), ("2026-10-02", 7)]),
          "traffic_clones": {
            "clones": [{"timestamp": "2026-10-02T00:00:00Z", "count": 2}]
          },
        },
        "xbrlkit": {"traffic_views": _traffic([("2026-10-03", 3)])},
        "xbrlkit-viewer": {"traffic_views": _traffic([("2026-10-03", 4)])},
      },
    )
    traffic = load_traffic(tmp_path)
    assert traffic["covered_from"] == "2026-09-07"
    assert traffic["repos"]["robosystems"]["views"]["2026-09-19"] == 5

    months = monthly_history({"github_traffic": traffic})
    assert "2026-09" not in months
    assert months["2026-10"]["rsx:GithubViews"] == 7
    assert months["2026-10"]["rsx:GithubClones"] == 2
    assert months["2026-10"]["rsx:XbrlkitGithubViews"] == 7

  def test_no_traffic_stored(self, tmp_path: Path) -> None:
    assert load_traffic(tmp_path / "missing") == {"repos": {}, "covered_from": None}
    assert monthly_history({"github_traffic": load_traffic(tmp_path)}) == {}


class TestSnapshotInstants:
  def test_robosystems_excludes_xbrlkit(self) -> None:
    observations = snapshot_instants(SNAPSHOT)
    assert observations["rsx:GithubStars"] == 22
    assert observations["rsx:GithubForks"] == 7
    assert observations["rsx:XbrlkitGithubStars"] == 13

  def test_registries_and_audiences(self) -> None:
    observations = snapshot_instants(SNAPSHOT)
    assert observations["rsx:DockerPulls"] == 38232
    assert observations["rsx:HuggingFaceDownloads"] == 169
    assert observations["rsx:YoutubeSubscribers"] == 15
    assert observations["rsx:XFollowers"] == 33

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


class TestCatalog:
  def test_every_emitted_concept_is_in_the_vocabulary(self) -> None:
    from integration.sources import CONCEPTS

    catalog = {c["qname"] for c in CONCEPTS}
    months = transform(SNAPSHOT, HISTORY)
    emitted = {concept for observations in months.values() for concept in observations}
    assert emitted <= catalog
    assert len(catalog) == len(CONCEPTS)


class TestLeadingZeros:
  def test_months_before_a_concept_first_appears_are_dropped(self) -> None:
    months = monthly_history(
      {
        "npm": {
          "@robosystems/mcp": [
            {"day": "2026-04-10", "downloads": 0},
            {"day": "2026-05-10", "downloads": 6},
            {"day": "2026-06-10", "downloads": 0},
          ]
        }
      }
    )
    assert "2026-04" not in months
    assert months["2026-05"]["rsx:NpmDownloads"] == 6
    assert months["2026-06"]["rsx:NpmDownloads"] == 0


class TestMergeAsserted:
  def test_a_failed_source_keeps_its_stored_value(self) -> None:
    stored = {"2026-08": {"rsx:PypiDownloads": 5104.0, "rsx:NpmDownloads": 5000.0}}
    fresh = {"2026-08": {"rsx:NpmDownloads": 5582.0}}
    assert merge_asserted(stored, fresh) == {
      "2026-08": {"rsx:PypiDownloads": 5104.0, "rsx:NpmDownloads": 5582.0}
    }

  def test_unchanged_months_are_skipped_and_new_months_kept(self) -> None:
    stored = {"2026-07": {"rsx:NpmDownloads": 10.0}}
    fresh = {"2026-07": {"rsx:NpmDownloads": 10.0}, "2026-09": {"rsx:XFollowers": 33.0}}
    assert merge_asserted(stored, fresh) == {"2026-09": {"rsx:XFollowers": 33.0}}
