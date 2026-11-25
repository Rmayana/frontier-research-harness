"""Bounded public literature queries and citation-addressable source reading."""
import hashlib
import json
import re
from typing import Literal
from urllib.parse import quote

from defusedxml import ElementTree as ET
import requests

from research_sources import fetch

Provider = Literal["europepmc", "pubmed", "openalex", "sportrxiv", "retractions",
                   "datacite", "jstage", "semantic-scholar", "arxiv-feed"]
SEARCH_PROVIDERS = {"europepmc", "pubmed", "openalex", "sportrxiv", "retractions",
                    "datacite", "jstage", "semantic-scholar", "arxiv-feed"}


def _public_fetch(provider, query, limit):
    try:
        return fetch(provider, query, limit)
    except requests.RequestException as exc:
        # Network exception messages can contain a provider credential in the URL.
        raise ValueError(f"{provider}: {type(exc).__name__}") from None


def _text(node):
    if node is None:
        return ""
    return " ".join("".join(node.itertext()).split())


def _id(value, pattern):
    match = re.fullmatch(pattern, str(value or ""), re.I)
    return match.group(1) if match else ""


def _row(title="", doi="", pmid="", pmc="", url="", source_id="", **extra):
    pmid = _id(pmid, r"(?:https?://pubmed\.ncbi\.nlm\.nih\.gov/)?(\d+)/?")
    pmc = _id(pmc, r"(?:PMC)?(\d+)")
    doi = re.sub(r"^https?://(?:dx\.)?doi\.org/", "", str(doi or ""), flags=re.I)[:400]
    read_ids = []
    if pmc:
        read_ids.append("PMC" + pmc)
    if pmid:
        read_ids.append("PMID:" + pmid)
    key = "DOI:" + doi if doi else next(iter(read_ids), source_id or url)
    canonical = "https://doi.org/" + quote(doi, safe="/:()") if doi else ""
    if pmid and not canonical:
        canonical = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"
    return {"citation_id": key, "read_ids": read_ids, "title": str(title or "")[:700],
            "url": str(url or canonical)[:1000], **extra}


def _results(provider, raw):
    if provider == "jstage":
        root = ET.fromstring(raw)
        for entry in root.findall("{*}entry"):
            link = entry.find("{*}link")
            yield _row(_text(entry.find("{*}title")), _text(entry.find("{*}doi")),
                       url=link.get("href", "") if link is not None else "",
                       source_id=_text(entry.find("{*}id")))
        return

    data = json.loads(raw)
    if provider == "pubmed":
        for pmid in data["esearchresult"]["idlist"]:
            yield _row(pmid=pmid)
    elif provider == "europepmc":
        for r in data["resultList"]["result"]:
            yield _row(r.get("title"), r.get("doi"), r.get("pmid"), r.get("pmcid"),
                       source_id=f"{r.get('source')}:{r.get('id')}")
    elif provider == "openalex":
        for r in data["results"]:
            ids = r.get("ids") or {}
            pmc = str(ids.get("pmcid") or "").rstrip("/").rsplit("/", 1)[-1]
            yield _row(r.get("display_name"), r.get("doi"), ids.get("pmid"), pmc,
                       source_id=r.get("id"), url=r.get("id"))
    elif provider in {"sportrxiv", "retractions"}:
        for r in data["message"]["items"]:
            targeted = [{"doi": str(x.get("DOI", ""))[:400], "type": x.get("type"),
                         "source": x.get("source")} for x in r.get("update-to", [])[:10]]
            yield _row(next(iter(r.get("title") or []), ""), r.get("DOI"), url=r.get("URL"),
                       **({"updates": targeted} if provider == "retractions" else {}))
    elif provider == "datacite":
        for r in data["data"]:
            attrs = r["attributes"]
            title = next(iter(attrs.get("titles") or []), {}).get("title", "")
            yield _row(title, r["id"], url=attrs.get("url"))
    elif provider == "semantic-scholar":
        for r in data["data"]:
            ids = r.get("externalIds") or {}
            yield _row(r.get("title"), ids.get("DOI"), ids.get("PubMed"), ids.get("PubMedCentral"),
                       url=r.get("url"), source_id=r.get("paperId"))
    else:
        for r in data:
            yield _row(r.get("title"), url=r.get("url"))


def search_papers(query: str, provider: Provider = "europepmc", limit: int = 5) -> dict:
    """Send a PUBLIC query to a named index. Returns metadata; use read_source for evidence.

    arxiv-feed takes an arXiv category (e.g. q-bio.QM). PubMed yields IDs; Europe PMC
    also yields titles. Only an entry's read_ids can be passed to read_source.
    """
    if provider not in SEARCH_PROVIDERS:
        raise ValueError("Unsupported public metadata provider")
    query = query.strip()
    if not 1 <= len(query) <= 500 or not 1 <= limit <= 20:
        raise ValueError("Use a public query of 1..500 characters and a limit of 1..20")
    if provider == "arxiv-feed" and not re.fullmatch(r"[A-Za-z][\w.-]{0,40}", query):
        raise ValueError("Use one arXiv category such as q-bio.QM")
    rows = list(_results(provider, _public_fetch(provider, query, limit)))[:limit]
    return {"provider": provider, "scope": "metadata", "results": rows}


def _body_blocks(node, path):
    """Preserve article order; retain JATS table row boundaries in table citations."""
    for index, child in enumerate(node, 1):
        tag = child.tag.rsplit("}", 1)[-1]
        locator = f"{path}/{tag}[{index}]"
        if tag == "sec":
            yield from _body_blocks(child, locator)
        elif tag == "table-wrap":
            label = _text(child.find("{*}label"))
            caption = _text(child.find("{*}caption"))
            rows = [" | ".join(_text(cell) for cell in row if cell.tag.rsplit("}", 1)[-1] in {"th", "td"})
                    for row in child.findall(".//{*}tr")]
            foot = _text(child.find("{*}table-wrap-foot"))
            yield locator, "\n".join(x for x in [label, caption, *rows, foot] if x)
        elif tag in {"title", "fig", "p", "disp-quote", "list"}:
            yield locator, _text(child)
        else:
            yield from _body_blocks(child, locator)


def read_source(source_id: str, offset: int = 0, max_chars: int = 6000) -> dict:
    """Read an indexed PubMed abstract or PMC body text. Reopen using offset and verify sha256.

    Figure images and supplements require separate inspection. Character offsets refer
    to the normalized text returned here, not a PDF's page numbering.
    """
    source_id = source_id.strip().upper()
    pmid = _id(source_id, r"PMID:(\d{1,12})")
    pmc = _id(source_id, r"PMC(\d{1,12})")
    if not (pmid or pmc) or offset < 0 or not 1 <= max_chars <= 16000:
        raise ValueError("Use PMID:<digits> or PMC<digits>, nonnegative offset, and 1..16000 characters")
    if pmid:
        root = ET.fromstring(_public_fetch("abstract", pmid, 1))
        article = root.find(".//{*}PubmedArticle")
        if article is None or _text(article.find("./{*}MedlineCitation/{*}PMID")) != pmid:
            raise ValueError("No matching PubMed record")
        title = _text(article.find(".//{*}ArticleTitle"))
        blocks = [(f"abstract/{i} {n.get('Label', '')}".strip(), _text(n)) for i, n in
                  enumerate(article.findall(".//{*}Article/{*}Abstract/{*}AbstractText"), 1)]
        scope = "abstract"
        url = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"
    else:
        root = ET.fromstring(_public_fetch("pmc-xml", source_id, 1))
        title = _text(root.find(".//{*}title-group/{*}article-title"))
        body = root.find("{*}body")
        blocks = list(_body_blocks(body, "body")) if body is not None else []
        scope = "full_text_body"
        url = f"https://pmc.ncbi.nlm.nih.gov/articles/{source_id}/"

    excerpts = []
    locators = []
    size = 0
    for locator, text in blocks:
        if not text:
            continue
        excerpt = text + "\n"
        excerpts.append(excerpt)
        end = size + len(excerpt)
        if size < offset + max_chars and end > offset:
            locators.append({"locator": locator, "start": max(offset, size), "end": min(end, offset + max_chars)})
        size = end
    if offset > size:
        raise ValueError("Offset beyond this source")
    document = "".join(excerpts)
    end = min(offset + max_chars, size)
    return {"source_id": source_id, "url": url, "title": title, "scope": scope if size else "metadata_only",
            "offset": offset, "next_offset": end if end < size else None, "total_chars": size,
            "sha256": hashlib.sha256(document.encode("utf-8")).hexdigest(),
            "locators": locators, "excerpt": document[offset:end]}
