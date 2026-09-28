"""Locators from fetched content, not additional evidence or scientific claims."""
from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import Any


def literature_navigation(record: dict[str, Any], limit: int = 100) -> dict[str, Any]:
    refs, links, sections = [], [], []
    raw = record.get("raw")
    if isinstance(raw, str):
        try:
            root = ET.fromstring(raw)
        except ET.ParseError:
            return {"status": "UNPARSEABLE", "note": "Exact fetched content retained; no navigation extracted."}
        for node in root.iter():
            tag = node.tag.rsplit("}", 1)[-1]
            if tag == "ref":
                refs.append({"locator": node.get("id"), "text": " ".join("".join(node.itertext()).split()),
                             "identifiers": [{"type": n.get("pub-id-type"), "id": n.text}
                                             for n in node.iter() if n.tag.rsplit("}", 1)[-1] == "pub-id"]})
            if tag == "sec":
                titles = [n for n in node if n.tag.rsplit("}", 1)[-1] == "title"]
                sections.append({"locator": node.get("id"), "title": "".join(titles[0].itertext()) if titles else None})
            href = node.get("{http://www.w3.org/1999/xlink}href") or node.get("href")
            if href:
                links.append({"element": tag, "href": href, "locator": node.get("id")})
    elif isinstance(raw, dict):
        refs = raw.get("reference", [])
        links = raw.get("link", [])
    return {"references": refs[:limit], "linked_material": links[:limit], "sections": sections[:limit],
            "counts": {"references": len(refs), "linked_material": len(links), "sections": len(sections)},
            "truncated": any(len(x) > limit for x in (refs, links, sections)),
            "note": "Navigation only. Linked papers, data, code and supplements have NOT been fetched or verified. Relative links require source-specific resolution."}
