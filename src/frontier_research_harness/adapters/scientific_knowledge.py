"""Direct scholarly-database clients for the Frontier Science workspace."""
from __future__ import annotations

import json
import socket
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any, Callable


JsonTransport = Callable[[str], dict[str, Any]]
TextTransport = Callable[[str], str]


def _get_json(url: str) -> dict[str, Any]:
    request = urllib.request.Request(url, headers={"User-Agent": "FrontierScienceModel/0.2"})
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def _get_text(url: str) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": "FrontierScienceModel/0.2"})
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read().decode("utf-8")


SOURCES: dict[str, dict[str, Any]] = {
    "pubmed": {
        "name": "PubMed",
        "base_url": "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/",
        "coverage": "Biomedical journal records indexed by NLM/MEDLINE.",
        "search": True,
        "fetch": True,
        "full_text": "Abstracts; full text only when linked through PMC/publisher.",
        "authentication": "No key required at low rate; NCBI API key optional.",
    },
    "europe_pmc": {
        "name": "Europe PMC",
        "base_url": "https://www.ebi.ac.uk/europepmc/webservices/rest/",
        "coverage": "Life-science articles, PubMed records, preprints, and open-access full text.",
        "search": True,
        "fetch": True,
        "full_text": "Open-access XML when a PMCID is available.",
        "authentication": "No key required.",
    },
    "crossref": {
        "name": "Crossref",
        "base_url": "https://api.crossref.org/works",
        "coverage": "DOI registration metadata, corrections, retractions, licenses, and publisher metadata.",
        "search": True,
        "fetch": True,
        "full_text": "Metadata and occasional abstracts; not a full-text database.",
        "authentication": "No key required for public pool.",
    },
    "clinical_trials": {
        "name": "ClinicalTrials.gov",
        "base_url": "https://clinicaltrials.gov/api/v2/studies",
        "coverage": "Registered interventional and observational studies, including recruitment status and submitted results.",
        "search": True,
        "fetch": True,
        "full_text": "Structured study registrations and submitted results; not journal full text.",
        "authentication": "No key required.",
    },
    "nsca": {
        "name": "NSCA research (PubMed-indexed)",
        "base_url": "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/",
        "coverage": "NSCA-associated peer-reviewed research indexed in PubMed, centered on the Journal of Strength and Conditioning Research.",
        "search": True,
        "fetch": True,
        "full_text": "PubMed records and abstracts; publisher access controls full text.",
        "authentication": "No key required at low rate; NCBI API key optional.",
        "limitation": "This is an explicit NSCA-focused PubMed view, not an NSCA private-content API.",
    },
}


class ScientificKnowledgeClient:
    def __init__(
        self,
        json_transport: JsonTransport = _get_json,
        text_transport: TextTransport = _get_text,
        *,
        max_attempts: int = 3,
        sleeper: Callable[[float], None] = time.sleep,
    ) -> None:
        if max_attempts < 1 or max_attempts > 6:
            raise ValueError("max_attempts must be between 1 and 6")
        self.json_transport = json_transport
        self.text_transport = text_transport
        self.max_attempts = max_attempts
        self.sleeper = sleeper

    @staticmethod
    def _is_transient(exc: BaseException) -> bool:
        if isinstance(exc, urllib.error.HTTPError):
            return exc.code in {408, 425, 429, 500, 502, 503, 504}
        return isinstance(
            exc,
            (urllib.error.URLError, TimeoutError, ConnectionError, socket.timeout),
        )

    def _request(self, transport: Callable[[str], Any], url: str) -> Any:
        """Retry only errors that are normally transient; never hide bad inputs."""
        for attempt in range(self.max_attempts):
            try:
                return transport(url)
            except Exception as exc:
                if not self._is_transient(exc) or attempt + 1 >= self.max_attempts:
                    raise
                self.sleeper(min(0.25 * (2**attempt), 2.0))
        raise AssertionError("unreachable")

    def list_sources(self) -> dict[str, Any]:
        return {"sources": [{"id": key, **value} for key, value in SOURCES.items()]}

    def search(
        self,
        source: str,
        query: str,
        limit: int = 10,
        *,
        cursor: str | None = None,
    ) -> dict[str, Any]:
        if source not in SOURCES:
            raise ValueError(f"unknown literature source: {source}")
        if not query.strip():
            raise ValueError("query must not be empty")
        if limit < 1 or limit > 50:
            raise ValueError("limit must be between 1 and 50")
        if cursor is not None and not isinstance(cursor, str):
            raise ValueError("cursor must be a string")
        if source == "pubmed":
            return self._search_pubmed(query, limit, cursor)
        if source == "nsca":
            filtered = f'({query}) AND "J Strength Cond Res"[jour]'
            result = self._search_pubmed(filtered, limit, cursor)
            return {**result, "source": "nsca", "query": query, "database_query": filtered}
        if source == "europe_pmc":
            return self._search_europe_pmc(query, limit, cursor)
        if source == "crossref":
            return self._search_crossref(query, limit, cursor)
        return self._search_clinical_trials(query, limit, cursor)

    def fetch(self, source: str, identifier: str) -> dict[str, Any]:
        if source not in SOURCES:
            raise ValueError(f"unknown literature source: {source}")
        if not identifier.strip():
            raise ValueError("identifier must not be empty")
        if source in {"pubmed", "nsca"}:
            url = SOURCES[source]["base_url"] + "efetch.fcgi?" + urllib.parse.urlencode({"db": "pubmed", "id": identifier, "retmode": "xml"})
            raw = self._request(self.text_transport, url)
            return {"source": source, "identifier": identifier, "format": "PubMed XML", "content_level": "record_with_abstract", "has_full_text": False, "raw": raw, "url": url}
        if source == "europe_pmc":
            encoded = urllib.parse.quote(identifier, safe="")
            result_url = f"{SOURCES[source]['base_url']}search?query={urllib.parse.quote('EXT_ID:'+identifier)}&format=json&pageSize=1"
            result = self._request(self.json_transport, result_url)
            records = result.get("resultList", {}).get("result", [])
            pmcid = records[0].get("pmcid") if records else None
            if pmcid:
                url = f"{SOURCES[source]['base_url']}{urllib.parse.quote(pmcid, safe='')}/fullTextXML"
                return {"source": source, "identifier": identifier, "format": "JATS XML", "content_level": "full_text", "has_full_text": True, "raw": self._request(self.text_transport, url), "url": url}
            return {"source": source, "identifier": identifier, "format": "metadata", "content_level": "metadata_only", "has_full_text": False, "raw": records[0] if records else None, "url": result_url, "limitation": "No open-access full text was available."}
        if source == "crossref":
            doi = identifier.removeprefix("https://doi.org/").removeprefix("doi:")
            url = f"{SOURCES[source]['base_url']}/{urllib.parse.quote(doi, safe='')}"
            return {"source": source, "identifier": doi, "format": "Crossref JSON", "content_level": "metadata_only", "has_full_text": False, "raw": self._request(self.json_transport, url).get("message"), "url": url}
        nct_id = identifier.upper()
        url = f"{SOURCES[source]['base_url']}/{urllib.parse.quote(nct_id, safe='')}"
        return {"source": source, "identifier": nct_id, "format": "ClinicalTrials.gov JSON", "content_level": "structured_registry_record", "has_full_text": False, "raw": self._request(self.json_transport, url), "url": url}

    @staticmethod
    def _page_fields(
        results: list[dict[str, Any]],
        *,
        total_count: int | None,
        next_cursor: str | None,
    ) -> dict[str, Any]:
        return {
            "results": results,
            "returned_count": len(results),
            "total_count": total_count,
            "next_cursor": next_cursor,
            "more_available": next_cursor is not None,
        }

    def _search_pubmed(self, query: str, limit: int, cursor: str | None) -> dict[str, Any]:
        base = SOURCES["pubmed"]["base_url"]
        try:
            offset = int(cursor or "0")
        except ValueError as exc:
            raise ValueError("PubMed cursor must be a non-negative integer string") from exc
        if offset < 0:
            raise ValueError("PubMed cursor must be a non-negative integer string")
        search_url = base + "esearch.fcgi?" + urllib.parse.urlencode({"db": "pubmed", "term": query, "retmode": "json", "retmax": limit, "retstart": offset, "sort": "relevance"})
        search = self._request(self.json_transport, search_url)
        search_result = search.get("esearchresult", {})
        ids = search_result.get("idlist", [])
        count_value = search_result.get("count")
        total_count = int(count_value) if str(count_value or "").isdigit() else None
        next_offset = offset + len(ids)
        more_known = total_count is not None and next_offset < total_count
        more_inferred = total_count is None and len(ids) == limit
        next_cursor = str(next_offset) if ids and (more_known or more_inferred) else None
        if not ids:
            return {"source": "pubmed", "query": query, **self._page_fields([], total_count=total_count, next_cursor=None), "search_url": search_url}
        summary_url = base + "esummary.fcgi?" + urllib.parse.urlencode({"db": "pubmed", "id": ",".join(ids), "retmode": "json"})
        summary = self._request(self.json_transport, summary_url).get("result", {})
        results = []
        for pmid in ids:
            item = summary.get(pmid, {})
            article_ids = {row.get("idtype"): row.get("value") for row in item.get("articleids", [])}
            results.append({"id": pmid, "pmid": pmid, "title": item.get("title"), "authors": [a.get("name") for a in item.get("authors", [])], "journal": item.get("fulljournalname"), "published": item.get("pubdate"), "doi": article_ids.get("doi"), "content_level": "metadata_only", "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"})
        return {"source": "pubmed", "query": query, **self._page_fields(results, total_count=total_count, next_cursor=next_cursor), "search_url": search_url}

    def _search_europe_pmc(self, query: str, limit: int, cursor: str | None) -> dict[str, Any]:
        params = {"query": query, "format": "json", "pageSize": limit, "resultType": "core", "cursorMark": cursor or "*"}
        url = SOURCES["europe_pmc"]["base_url"] + "search?" + urllib.parse.urlencode(params)
        payload = self._request(self.json_transport, url)
        results = [{"id": item.get("id") or item.get("extId"), "pmid": item.get("pmid"), "pmcid": item.get("pmcid"), "doi": item.get("doi"), "title": item.get("title"), "authors": item.get("authorString"), "journal": item.get("journalTitle"), "published": item.get("firstPublicationDate"), "cited_by_count": item.get("citedByCount"), "is_open_access": item.get("isOpenAccess"), "publication_type": item.get("pubType"), "content_level": "metadata_only", "url": f"https://europepmc.org/article/{item.get('source','MED')}/{item.get('id') or item.get('extId')}"} for item in payload.get("resultList", {}).get("result", [])]
        candidate = payload.get("nextCursorMark")
        next_cursor = candidate if results and candidate and candidate != (cursor or "*") else None
        total = payload.get("hitCount")
        return {"source": "europe_pmc", "query": query, **self._page_fields(results, total_count=int(total) if isinstance(total, int) or str(total or "").isdigit() else None, next_cursor=next_cursor), "search_url": url}

    def _search_crossref(self, query: str, limit: int, cursor: str | None) -> dict[str, Any]:
        url = SOURCES["crossref"]["base_url"] + "?" + urllib.parse.urlencode({"query": query, "rows": limit, "cursor": cursor or "*", "select": "DOI,title,author,published,container-title,type,URL,is-referenced-by-count,update-to"})
        payload = self._request(self.json_transport, url)
        results = []
        for item in payload.get("message", {}).get("items", []):
            authors = [" ".join(part for part in (author.get("given"), author.get("family")) if part) for author in item.get("author", [])]
            results.append({"id": item.get("DOI"), "doi": item.get("DOI"), "title": (item.get("title") or [None])[0], "authors": authors, "journal": (item.get("container-title") or [None])[0], "published": item.get("published"), "type": item.get("type"), "cited_by_count": item.get("is-referenced-by-count"), "updates": item.get("update-to", []), "content_level": "metadata_only", "url": item.get("URL")})
        message = payload.get("message", {})
        candidate = message.get("next-cursor")
        next_cursor = candidate if results and candidate and candidate != (cursor or "*") else None
        total = message.get("total-results")
        return {"source": "crossref", "query": query, **self._page_fields(results, total_count=int(total) if isinstance(total, int) else None, next_cursor=next_cursor), "search_url": url}

    def _search_clinical_trials(self, query: str, limit: int, cursor: str | None) -> dict[str, Any]:
        params = {"query.term": query, "pageSize": limit, "format": "json", "countTotal": "true"}
        if cursor:
            params["pageToken"] = cursor
        url = SOURCES["clinical_trials"]["base_url"] + "?" + urllib.parse.urlencode(params)
        payload = self._request(self.json_transport, url)
        results = []
        for study in payload.get("studies", []):
            protocol = study.get("protocolSection", {})
            identity = protocol.get("identificationModule", {})
            status = protocol.get("statusModule", {})
            design = protocol.get("designModule", {})
            nct_id = identity.get("nctId")
            results.append({
                "id": nct_id,
                "title": identity.get("briefTitle") or identity.get("officialTitle"),
                "overall_status": status.get("overallStatus"),
                "study_type": design.get("studyType"),
                "phases": design.get("phases", []),
                "has_results": study.get("hasResults", False),
                "content_level": "metadata_only",
                "url": f"https://clinicaltrials.gov/study/{nct_id}" if nct_id else None,
            })
        next_cursor = payload.get("nextPageToken") if results else None
        total = payload.get("totalCount")
        return {"source": "clinical_trials", "query": query, **self._page_fields(results, total_count=int(total) if isinstance(total, int) else None, next_cursor=next_cursor), "search_url": url}


__all__ = ["SOURCES", "ScientificKnowledgeClient"]
