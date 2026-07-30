"""The Growth Metrics vocabulary — authored once, resolved thereafter.

A ``block_type='metric'`` structure with one concept per series and NO
Derive rules (asserted structures stay disjoint from computed ones —
the platform rejects asserting into a rule-carrying structure).
``ensure_structure`` is idempotent: it resolves the structure by name
via GraphQL and only authors it when absent.
"""

from __future__ import annotations

from integration.client import IntegrationClient
from integration.emit.metrics import author_metric_structure
from integration.sources import ABSTRACT_QNAME, CONCEPTS, STRUCTURE_NAME


def _find_structure_id(client: IntegrationClient) -> str | None:
  data = client.graphql('{ informationBlocks(blockType: "metric") { id name } }')
  for block in data.get("informationBlocks") or []:
    if block.get("name") == STRUCTURE_NAME:
      return block["id"]
  return None


def _rs_gaap_taxonomy_id(client: IntegrationClient) -> str:
  data = client.graphql(
    '{ taxonomies(taxonomyType: "reporting_standard") { taxonomies { id standard } } }'
  )
  for taxonomy in (data.get("taxonomies") or {}).get("taxonomies") or []:
    if str(taxonomy.get("standard", "")).startswith("rs-gaap"):
      return taxonomy["id"]
  raise RuntimeError("rs-gaap reporting standard not found in graph")


def ensure_structure(client: IntegrationClient) -> str:
  """Return the Growth Metrics structure id, authoring it if needed."""
  existing = _find_structure_id(client)
  if existing:
    return existing

  author_metric_structure(
    client,
    name=STRUCTURE_NAME,
    parent_taxonomy_id=_rs_gaap_taxonomy_id(client),
    abstract_qname=ABSTRACT_QNAME,
    concepts=CONCEPTS,
    description=(
      "RFS marketing/usage metrics observed from public APIs — GitHub, "
      "npm, PyPI, Docker Hub — asserted monthly by "
      "robosystems-marketing-integration."
    ),
  )
  structure_id = _find_structure_id(client)
  if structure_id is None:
    raise RuntimeError("structure not found after authoring")
  return structure_id
