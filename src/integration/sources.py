"""The tracked-asset catalog — which public artifacts feed the series.

Everything here is collectable without credentials (public APIs).
GitHub *traffic* (views/clones) additionally needs a PAT with push
access — set ``GITHUB_TOKEN`` in the environment and the collector
picks it up; without it, traffic is skipped. Traffic is the perishable
source: the API retains only 14 days, so history exists only if this
integration keeps snapshotting it.
"""

from __future__ import annotations

GITHUB_ORG = "RoboFinSystems"
GITHUB_REPOS = [
  "robosystems",
  "robosystems-mcp-client",
  "robosystems-typescript-client",
  "robosystems-python-client",
  "robosystems-xbrl-holon",
]

NPM_PACKAGES = ["@robosystems/mcp", "@robosystems/core"]

PYPI_PACKAGES = ["robosystems-client", "robosystems-xbrl-holon"]

DOCKER_REPOS = ["robofinsystems/robosystems"]

# The metric vocabulary — one concept per series, asserted monthly.
# Instant concepts land as of period_end; duration concepts cover the
# month. Authored once via create-taxonomy-block (see vocabulary.py).
STRUCTURE_NAME = "RFS Growth Metrics"
ABSTRACT_QNAME = "rsx:GrowthMetricsAbstract"
CONCEPTS = [
  {"qname": "rsx:GithubStars", "name": "GitHub Stars", "period_type": "instant"},
  {"qname": "rsx:GithubForks", "name": "GitHub Forks", "period_type": "instant"},
  {"qname": "rsx:NpmDownloads", "name": "npm Downloads", "period_type": "duration"},
  {"qname": "rsx:PypiDownloads", "name": "PyPI Downloads", "period_type": "duration"},
  {"qname": "rsx:DockerPulls", "name": "Docker Pulls", "period_type": "instant"},
]
