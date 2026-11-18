from __future__ import annotations

from datetime import date

import pytest

from integration import collect


def test_buffer_maps_channels_by_handle_and_skips_others(
  monkeypatch: pytest.MonkeyPatch,
) -> None:
  monkeypatch.setenv("BUFFER_API_KEY", "test")
  monkeypatch.setattr(collect, "_today", lambda: date(2026, 11, 18))
  channels = [
    {"id": "li", "service": "linkedin", "name": "josephtfrench"},
    {"id": "x-company", "service": "twitter", "name": "robofinsystems"},
    {"id": "x-personal", "service": "twitter", "name": "JosephTFrench"},
  ]
  impressions = {"li": 100, "x-company": 7, "x-personal": 999}

  def fake_buffer(query: str) -> dict:
    if "organizations" in query:
      return {"account": {"organizations": [{"id": "org"}]}}
    if "channels(" in query:
      return {"channels": channels}
    channel_id = query.split('channelIds: ["')[1].split('"')[0]
    return {
      "aggregatedPostMetrics": {
        "metrics": [
          {"type": "postCount", "value": 1},
          {"type": "impressions", "value": impressions[channel_id]},
        ]
      }
    }

  monkeypatch.setattr(collect, "_buffer", fake_buffer)
  history = collect.history_buffer()

  assert set(history) == {"rsx:LinkedinImpressions", "rsx:XPostImpressions"}
  assert history["rsx:XPostImpressions"]["2026-11"]["impressions"] == 7
  assert history["rsx:LinkedinImpressions"]["2026-11"]["impressions"] == 100
