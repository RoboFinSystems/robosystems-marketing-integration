"""The tracked-asset catalog — which public artifacts feed the series.

The no-auth sources (GitHub repo stats, npm, PyPI, Docker Hub, Hugging
Face) always run. Every credentialed source is optional: without its
environment variables it is skipped, and its concepts simply get no
value that month.

- ``GITHUB_TOKEN`` — PAT with push access; enables repo traffic. The
  perishable source: the API retains only 14 days, so history exists
  only because ``data/`` persists run over run.
- ``CLOUDFLARE_ACCOUNT_ID`` + ``CLOUDFLARE_API_TOKEN`` — Web Analytics
  (retains ~6 months).
- ``GOOGLE_CLIENT_ID`` / ``GOOGLE_CLIENT_SECRET`` /
  ``GOOGLE_REFRESH_TOKEN`` — one read-only OAuth grant covering Search
  Console and YouTube. ``GSC_*`` / ``YOUTUBE_*`` override per service.
- ``X_BEARER_TOKEN`` — X API v2 app token.
- ``BUFFER_API_KEY`` — Buffer post analytics (LinkedIn, X).

xbrlkit is its own product, so its artifacts feed their own concepts;
every "RoboSystems" concept excludes it.
"""

from __future__ import annotations

GITHUB_ORG = "RoboFinSystems"
GITHUB_REPOS = [
  "robosystems",
  "robosystems-mcp-client",
  "robosystems-typescript-client",
  "robosystems-python-client",
]
XBRLKIT_REPO = "xbrlkit"

NPM_PACKAGES = ["@robosystems/mcp", "@robosystems/core"]

PYPI_PACKAGE = "robosystems-client"
XBRLKIT_PYPI_PACKAGE = "xbrlkit"

DOCKER_REPOS = ["robofinsystems/robosystems"]

HUGGINGFACE_DATASETS = ["robosystems/sec-xbrl-knowledge-graphs"]

# Cloudflare Web Analytics host → concept-name stem.
SITES = {
  "robosystems.ai": "Robosystems",
  "roboledger.ai": "Roboledger",
  "roboinvestor.ai": "Roboinvestor",
  "xbrlkit.com": "Xbrlkit",
  "harbinger.finance": "Harbinger",
}

SEARCH_CONSOLE_PROPERTIES = [f"sc-domain:{host}" for host in SITES]

X_HANDLE = "RoboFinSystems"

# Buffer channel service → concept.
BUFFER_CHANNELS = {
  "linkedin": "rsx:LinkedinImpressions",
  "twitter": "rsx:XPostImpressions",
}

# The metric vocabulary — one concept per series, asserted monthly.
# Instant concepts land as of period_end; duration concepts cover the
# month. Authored once via create-taxonomy-block (see vocabulary.py).
STRUCTURE_NAME = "RFS Growth Metrics"
ABSTRACT_QNAME = "rsx:GrowthMetricsAbstract"


def _site_concepts() -> list[dict]:
  concepts = []
  for host, stem in SITES.items():
    concepts.append(
      {
        "qname": f"rsx:{stem}SitePageViews",
        "name": f"Site Page Views — {host}",
        "period_type": "duration",
      }
    )
    concepts.append(
      {
        "qname": f"rsx:{stem}SiteVisits",
        "name": f"Site Visits — {host}",
        "period_type": "duration",
      }
    )
  return concepts


CONCEPTS = [
  {
    "qname": "rsx:GithubStars",
    "name": "GitHub Stars — RoboSystems",
    "period_type": "instant",
  },
  {
    "qname": "rsx:GithubForks",
    "name": "GitHub Forks — RoboSystems",
    "period_type": "instant",
  },
  {
    "qname": "rsx:GithubViews",
    "name": "GitHub Repo Views — RoboSystems",
    "period_type": "duration",
  },
  {
    "qname": "rsx:GithubClones",
    "name": "GitHub Repo Clones — RoboSystems",
    "period_type": "duration",
  },
  {"qname": "rsx:NpmDownloads", "name": "npm Downloads", "period_type": "duration"},
  {
    "qname": "rsx:PypiDownloads",
    "name": "PyPI Downloads — robosystems-client",
    "period_type": "duration",
  },
  {"qname": "rsx:DockerPulls", "name": "Docker Pulls", "period_type": "instant"},
  {
    "qname": "rsx:XbrlkitGithubStars",
    "name": "GitHub Stars — xbrlkit",
    "period_type": "instant",
  },
  {
    "qname": "rsx:XbrlkitGithubViews",
    "name": "GitHub Repo Views — xbrlkit",
    "period_type": "duration",
  },
  {
    "qname": "rsx:XbrlkitPypiDownloads",
    "name": "PyPI Downloads — xbrlkit",
    "period_type": "duration",
  },
  {
    "qname": "rsx:HuggingFaceDownloads",
    "name": "Hugging Face Dataset Downloads",
    "period_type": "instant",
  },
  *_site_concepts(),
  {
    "qname": "rsx:SearchImpressions",
    "name": "Google Search Impressions",
    "period_type": "duration",
  },
  {
    "qname": "rsx:SearchClicks",
    "name": "Google Search Clicks",
    "period_type": "duration",
  },
  {"qname": "rsx:YoutubeViews", "name": "YouTube Views", "period_type": "duration"},
  {
    "qname": "rsx:YoutubeWatchMinutes",
    "name": "YouTube Watch Minutes",
    "period_type": "duration",
  },
  {
    "qname": "rsx:YoutubeSubscribers",
    "name": "YouTube Subscribers",
    "period_type": "instant",
  },
  {
    "qname": "rsx:XFollowers",
    "name": "X Followers — @RoboFinSystems",
    "period_type": "instant",
  },
  {
    "qname": "rsx:LinkedinImpressions",
    "name": "LinkedIn Post Impressions",
    "period_type": "duration",
  },
  {
    "qname": "rsx:XPostImpressions",
    "name": "X Post Impressions (Buffer)",
    "period_type": "duration",
  },
]
