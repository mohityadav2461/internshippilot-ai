"""Public RSS / Atom feeds. Feed URLs are configured per source; nothing is hard-coded."""

from __future__ import annotations

import xml.etree.ElementTree as ET

from ..http_client import PoliteClient, SourceError
from ..models import RawJob

ATOM = "{http://www.w3.org/2005/Atom}"


def fetch(config: dict, client: PoliteClient, source_name: str) -> list[RawJob]:
    feeds = [str(u) for u in (config.get("feed_urls") or []) if isinstance(u, str)][:10]
    location = str(config.get("location") or "")
    fixed_company = str(config.get("company") or "").strip()
    out: list[RawJob] = []
    for feed_url in feeds:
        body = client.get(feed_url).text
        try:
            root = ET.fromstring(body)
        except ET.ParseError as exc:
            raise SourceError("feed is not valid XML") from exc
        channel_title = (root.findtext("channel/title") or root.findtext(f"{ATOM}title") or "").strip()
        company = fixed_company or channel_title
        if not company:
            raise SourceError("feed has no company name; set 'company' in the source config")
        for item in root.iter("item"):
            out.append(RawJob(
                source_name=source_name,
                company=company,
                title=(item.findtext("title") or "").strip(),
                url=(item.findtext("link") or "").strip(),
                location=location,
                description_html=item.findtext("description") or "",
                posted_at=item.findtext("pubDate"),
            ))
        for entry in root.iter(f"{ATOM}entry"):
            link = entry.find(f"{ATOM}link")
            out.append(RawJob(
                source_name=source_name,
                company=company,
                title=(entry.findtext(f"{ATOM}title") or "").strip(),
                url=(link.get("href") if link is not None else "") or "",
                location=location,
                description_html=entry.findtext(f"{ATOM}summary") or entry.findtext(f"{ATOM}content") or "",
                posted_at=entry.findtext(f"{ATOM}published"),
            ))
    return out
