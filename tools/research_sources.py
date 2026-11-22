"""Read one public/authorized research source. Run with the project tools interpreter."""
import argparse
import json
import os
from urllib.parse import quote, urlsplit
import sys

import feedparser
import requests

PROVIDERS = (
    "pubmed", "abstract", "europepmc", "pmc-xml", "bioc", "datacite", "retractions",
    "openalex", "semantic-scholar", "sportrxiv", "jstage", "arxiv-feed", "feed", "youtube", "zotero",
)


def endpoint(name, term, limit):
    ncbi = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/"
    epmc = "https://www.ebi.ac.uk/europepmc/webservices/rest/"
    escaped = quote(term, safe="")
    headers = {}
    if name in {"pubmed", "abstract"}:
        params = {"db": "pubmed", "tool": "frontier_training_research"}
        if os.getenv("NCBI_API_KEY"):
            params["api_key"] = os.environ["NCBI_API_KEY"]
        if name == "pubmed":
            return ncbi + "esearch.fcgi", dict(params, term=term, retmode="json", retmax=limit), headers
        return ncbi + "efetch.fcgi", dict(params, id=term, retmode="xml"), headers
    if name == "europepmc":
        return epmc + "search", dict(query=term, format="json", pageSize=limit), headers
    if name == "pmc-xml":
        return epmc + escaped + "/fullTextXML", {}, headers
    if name == "bioc":
        return "https://www.ncbi.nlm.nih.gov/research/bionlp/RESTful/pmcoa.cgi/BioC_json/" + escaped + "/unicode", {}, headers
    if name == "datacite":
        return "https://api.datacite.org/dois", {"query": term, "page[size]": limit}, headers
    if name == "retractions":
        return "https://api.crossref.org/works", {"filter": "update-type:retraction", "query.bibliographic": term, "rows": limit}, headers
    if name == "sportrxiv":
        return "https://api.crossref.org/works", {"filter": "prefix:10.51224", "query.bibliographic": term, "rows": limit}, headers
    if name == "openalex":
        params = {"search": term, "per_page": limit}
        if os.getenv("OPENALEX_API_KEY"):
            params["api_key"] = os.environ["OPENALEX_API_KEY"]
        return "https://api.openalex.org/works", params, headers
    if name == "semantic-scholar":
        if os.getenv("S2_API_KEY"):
            headers["x-api-key"] = os.environ["S2_API_KEY"]
        return "https://api.semanticscholar.org/graph/v1/paper/search", {"query": term, "fields": "title,url,externalIds", "limit": limit}, headers
    if name == "jstage":
        return "https://api.jstage.jst.go.jp/searchapi/do", {"service": "3", "article": term, "count": limit}, headers
    if name == "arxiv-feed":
        return "https://rss.arxiv.org/rss/" + escaped, {}, headers
    if name == "feed":
        if urlsplit(term).scheme != "https":
            raise ValueError("Supply an HTTPS RSS or Atom URL")
        return term, {}, headers
    if name == "youtube":
        if not os.getenv("YOUTUBE_API_KEY"):
            raise ValueError("YOUTUBE_API_KEY required")
        headers["X-Goog-Api-Key"] = os.environ["YOUTUBE_API_KEY"]
        return "https://www.googleapis.com/youtube/v3/search", {"part": "snippet", "type": "video", "q": term, "maxResults": limit}, headers
    library = os.getenv("ZOTERO_LIBRARY_ID", "")
    kind = os.getenv("ZOTERO_LIBRARY_TYPE", "users")
    if not library.isdecimal() or kind not in {"users", "groups"}:
        raise ValueError("Set ZOTERO_LIBRARY_ID and ZOTERO_LIBRARY_TYPE (users/groups)")
    if os.getenv("ZOTERO_API_KEY"):
        headers["Zotero-API-Key"] = os.environ["ZOTERO_API_KEY"]
    return f"https://api.zotero.org/{kind}/{library}/items", {"q": term, "limit": limit}, headers


def fetch(name, term, limit):
    url, params, headers = endpoint(name, term, limit)
    with requests.get(url, params=params, headers=headers, timeout=(10, 40)) as response:
        if response.status_code != 200:
            raise ValueError(f"{name}: HTTP {response.status_code}")
        if name in {"arxiv-feed", "feed"}:
            feed = feedparser.parse(response.content)
            if not feed.version:
                raise ValueError(f"{name}: response is not RSS/Atom")
            return json.dumps([{"title": e.get("title"), "url": e.get("link")} for e in feed.entries[:limit]], ensure_ascii=False)
        if name in {"jstage", "abstract", "pmc-xml"}:
            from defusedxml import ElementTree
            root = ElementTree.fromstring(response.content)
            if root.tag.split("}")[-1] not in {"feed", "PubmedArticleSet", "article"}:
                raise ValueError(f"{name}: unexpected document")
            if name == "jstage":
                status = next((n.text for n in root.iter() if n.tag.split("}")[-1] == "status"), None)
                if status and status.upper() not in {"0", "OK", "SUCCESS"} and not status.startswith("WARN_"):
                    raise ValueError(f"jstage: API status {status}")
            return response.content.decode(response.encoding if response.encoding and response.encoding.lower() != "iso-8859-1" else "utf-8")
        return json.dumps(response.json(), ensure_ascii=False)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("provider", choices=PROVIDERS)
    parser.add_argument("term", help="public query, identifier, category, or RSS URL")
    parser.add_argument("--limit", type=int, choices=range(1, 51), default=5, metavar="1..50")
    args = parser.parse_args()
    try:
        print(fetch(args.provider, args.term, args.limit))
    except (requests.RequestException, ValueError) as exc:
        # Requests errors may include a private query or a provider key in a URL.
        parser.exit(1, f"{args.provider}: {type(exc).__name__ if isinstance(exc, requests.RequestException) else exc}\n")
