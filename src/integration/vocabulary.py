"""The Growth Metrics vocabulary — authored once, resolved thereafter.

A ``block_type='metric'`` structure with one concept per series and NO
Derive rules (asserted structures stay disjoint from computed ones —
the platform rejects asserting into a rule-carrying structure).
``ensure_structure`` is idempotent: it resolves the structure by name
via GraphQL and only authors it when absent. It never extends an
existing structure — a concept added to ``CONCEPTS`` after the first
run is reported as missing and left unasserted until it is authored
onto the structure (``update-taxonomy-block``).
"""

from __future__ import annotations

from integration.client import IntegrationClient
from integration.emit.metrics import author_metric_structure
from integration.sources import ABSTRACT_QNAME, CONCEPTS, STRUCTURE_NAME


def _find_structure(client: IntegrationClient) -> tuple[str, set[str]] | None:
  data = client.graphql(
    '{ informationBlocks(blockType: "metric") { id name elements { qname } } }'
  )
  for block in data.get("informationBlocks") or []:
    if block.get("name") == STRUCTURE_NAME:
      return block["id"], {e["qname"] for e in block.get("elements") or []}
  return None


def asserted_values(client: IntegrationClient) -> dict[str, dict[str, float]]:
  """The values already on the structure, as ``{month: {qname: value}}``."""
  data = client.graphql(
    '{ informationBlocks(blockType: "metric") '
    "{ name facts { elementQname value periodEnd } } }"
  )
  months: dict[str, dict[str, float]] = {}
  for block in data.get("informationBlocks") or []:
    if block.get("name") != STRUCTURE_NAME:
      continue
    for fact in block.get("facts") or []:
      if fact.get("value") is not None:
        month = str(fact["periodEnd"])[:7]
        months.setdefault(month, {})[fact["elementQname"]] = float(fact["value"])
  return months


def _rs_gaap_taxonomy_id(client: IntegrationClient) -> str:
  data = client.graphql(
    '{ taxonomies(taxonomyType: "reporting_standard") { taxonomies { id standard } } }'
  )
  for taxonomy in (data.get("taxonomies") or {}).get("taxonomies") or []:
    if str(taxonomy.get("standard", "")).startswith("rs-gaap"):
      return taxonomy["id"]
  raise RuntimeError("rs-gaap reporting standard not found in graph")


def ensure_structure(client: IntegrationClient) -> tuple[str, set[str]]:
  """Return the Growth Metrics structure id and its concept qnames,
  authoring the structure if needed."""
  existing = _find_structure(client)
  if existing:
    return existing

  author_metric_structure(
    client,
    name=STRUCTURE_NAME,
    parent_taxonomy_id=_rs_gaap_taxonomy_id(client),
    abstract_qname=ABSTRACT_QNAME,
    concepts=CONCEPTS,
    description=(
      "RFS marketing and usage metrics — code distribution, site "
      "traffic, search, video and social reach — observed from their "
      "source APIs and asserted monthly by robosystems-marketing-integration."
    ),
  )
  authored = _find_structure(client)
  if authored is None:
    raise RuntimeError("structure not found after authoring")
  return authored
