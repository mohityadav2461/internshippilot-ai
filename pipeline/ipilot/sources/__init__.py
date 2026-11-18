"""Adapter registry. Each adapter takes (config, client, source_name) and returns RawJob objects."""

from . import ashby, greenhouse, jsonld, lever, rss

ADAPTERS = {
    "greenhouse": greenhouse.fetch,
    "lever": lever.fetch,
    "ashby": ashby.fetch,
    "rss": rss.fetch,
    "jsonld_pages": jsonld.fetch,
}
