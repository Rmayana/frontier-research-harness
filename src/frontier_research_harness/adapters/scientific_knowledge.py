"""Direct scholarly-database clients for the Frontier Science workspace."""
from __future__ import annotations

import json
import re
import socket
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
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
    "openalex": {
        "name": "OpenAlex",
        "base_url": "https://api.openalex.org/works",
        "coverage": "Scholarly work metadata, citation relationships, and open-access locations.",
        "search": True,
        "fetch": True,
        "full_text": "Metadata and abstract indexes only; linked full text is not downloaded.",
        "authentication": "Anonymous basic use; this client does not attach keys or enable paid usage.",
        "usage_policy_url": "https://help.openalex.org/api/authentication/",
    },
    "zenodo": {
        "name": "Zenodo published records",
        "base_url": "https://zenodo.org/api/records",
        "coverage": "Published datasets, software, model files, and research outputs.",
        "search": True,
        "fetch": True,
        "full_text": "Record metadata and file manifests only; file contents are not downloaded.",
        "authentication": "Public published-record endpoints; restricted files require separate authorization.",
        "max_search_limit": 25,
        "api_documentation_url": "https://developers.zenodo.org/#records",
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
        if type(limit) is not int or limit < 1 or limit > 50:
            raise ValueError("limit must be between 1 and 50")
        if source == "zenodo" and limit > 25:
            raise ValueError("Zenodo anonymous search limit must be between 1 and 25")
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
        if source == "openalex":
            return self._search_openalex(query, limit, cursor)
        if source == "zenodo":
            return self._search_zenodo(query, limit, cursor)
        return self._search_clinical_trials(query, limit, cursor)

    def fetch(self, source: str, identifier: str) -> dict[str, Any]:
        if source not in SOURCES:
            raise ValueError(f"unknown literature source: {source}")
        if not identifier.strip():
            raise ValueError("identifier must not be empty")
        if source in {"pubmed", "nsca"}:
            url = SOURCES[source]["base_url"] + "efetch.fcgi?" + urllib.parse.urlencode({"db": "pubmed", "id": identifier, "retmode": "xml"})
            raw = self._request(self.text_transport, url)
            record = {
                "source": source,
                "identifier": identifier,
                "format": "PubMed XML",
                "content_level": "record_with_abstract",
                "has_full_text": False,
                "raw": raw,
                "url": url,
            }
            pmcid = self._pubmed_pmcid(raw)
            if not pmcid:
                return record
            full_text_url = (
                f"{SOURCES['europe_pmc']['base_url']}"
                f"{urllib.parse.quote(pmcid, safe='')}/fullTextXML"
            )
            try:
                full_text = self._request(self.text_transport, full_text_url)
                self._validate_full_text(full_text)
            except Exception as exc:
                return {
                    **record,
                    "pmcid": pmcid,
                    "full_text_resolution": {
                        "attempted": True,
                        "resolved": False,
                        "error_type": type(exc).__name__,
                        "error": str(exc),
                    },
                }
            return {
                "source": source,
                "identifier": identifier,
                "pmcid": pmcid,
                "format": "JATS XML",
                "content_level": "full_text",
                "has_full_text": True,
                "raw": full_text,
                "url": full_text_url,
                "source_record": record,
                "full_text_resolution": {
                    "attempted": True,
                    "resolved": True,
                    "resolver": "Europe PMC",
                },
            }
        if source == "europe_pmc":
            normalized = identifier.strip()
            if re.fullmatch(r"PMC\d+", normalized, re.IGNORECASE):
                database_query = f"PMCID:{normalized.upper()}"
            elif re.fullmatch(r"(?:PMID:)?\d+", normalized, re.IGNORECASE):
                database_query = f"EXT_ID:{normalized.split(':')[-1]} AND SRC:MED"
            else:
                doi = re.sub(r"^(?:https?://(?:dx\.)?doi\.org/|doi:)", "", normalized, flags=re.IGNORECASE)
                if not re.fullmatch(r"10\.\d{4,9}/[^\s\"]+", doi):
                    raise ValueError("Europe PMC identifier must be a PMID, PMCID, or DOI")
                database_query = f'DOI:"{doi}"'
            result_url = SOURCES[source]["base_url"] + "search?" + urllib.parse.urlencode({"query": database_query, "format": "json", "pageSize": 1, "resultType": "core"})
            result = self._request(self.json_transport, result_url)
            records = result.get("resultList", {}).get("result", [])
            pmcid = records[0].get("pmcid") if records else None
            if pmcid and not re.fullmatch(r"PMC\d+", str(pmcid), re.IGNORECASE):
                raise ValueError("Europe PMC returned an invalid PMCID")
            if pmcid:
                pmcid = pmcid.upper()
            record = {"source": source, "identifier": identifier, "format": "metadata", "content_level": "record_with_abstract" if records and records[0].get("abstractText") else "metadata_only", "has_full_text": False, "raw": records[0] if records else None, "url": result_url}
            if pmcid:
                url = f"{SOURCES[source]['base_url']}{urllib.parse.quote(pmcid, safe='')}/fullTextXML"
                try:
                    raw = self._request(self.text_transport, url)
                    self._validate_full_text(raw)
                except Exception as exc:
                    return {**record, "pmcid": pmcid, "full_text_resolution": {"attempted": True, "resolved": False, "error_type": type(exc).__name__, "error": str(exc)}, "limitation": "Full text could not be retrieved; metadata or abstract only."}
                return {**record, "pmcid": pmcid, "format": "JATS XML", "content_level": "full_text", "has_full_text": True, "raw": raw, "url": url, "source_record": record, "full_text_resolution": {"attempted": True, "resolved": True, "resolver": "Europe PMC"}}
            return {**record, "full_text_resolution": {"attempted": False, "resolved": False}, "limitation": "No PMCID was returned for this identifier; full-text availability elsewhere is unknown."}
        if source == "openalex":
            work_id = self._openalex_identifier(identifier)
            url = SOURCES[source]["base_url"] + "/" + urllib.parse.quote(work_id, safe=":/")
            raw = self._request(self.json_transport, url)
            return {"source": source, "identifier": work_id, "format": "OpenAlex JSON", "content_level": "metadata_only", "has_full_text": False, "raw": raw, "record": self._openalex_record(raw), "url": url, "limitation": "Linked locations and abstract indexes are metadata, not retrieved full text."}
        if source == "zenodo":
            record_id = self._zenodo_identifier(identifier)
            url = SOURCES[source]["base_url"] + "/" + record_id
            raw = self._request(self.json_transport, url)
            return {"source": source, "identifier": record_id, "format": "Zenodo JSON", "content_level": "metadata_only", "has_full_text": False, "raw": raw, "record": self._zenodo_record(raw), "url": url, "limitation": "File manifest only; no dataset, model, or document file has been downloaded."}
        if source == "crossref":
            doi = identifier.removeprefix("https://doi.org/").removeprefix("doi:")
            url = f"{SOURCES[source]['base_url']}/{urllib.parse.quote(doi, safe='')}"
            return {"source": source, "identifier": doi, "format": "Crossref JSON", "content_level": "metadata_only", "has_full_text": False, "raw": self._request(self.json_transport, url).get("message"), "url": url}
        nct_id = identifier.upper()
        url = f"{SOURCES[source]['base_url']}/{urllib.parse.quote(nct_id, safe='')}"
        return {"source": source, "identifier": nct_id, "format": "ClinicalTrials.gov JSON", "content_level": "structured_registry_record", "has_full_text": False, "raw": self._request(self.json_transport, url), "url": url}

    @staticmethod
    def _validate_full_text(raw: str) -> None:
        """Do not promote a successful HTTP error page or abstract-only XML to full text."""
        try:
            root = ET.fromstring(raw)
        except ET.ParseError as exc:
            raise ValueError("full-text endpoint did not return valid article XML") from exc
        if root.tag.split("}")[-1] not in {"article", "article-set"} or not any(
            element.tag.split("}")[-1] == "body" and "".join(element.itertext()).strip()
            for element in root.iter()
        ):
            raise ValueError("full-text endpoint did not return an article body")

    @staticmethod
    def _pubmed_pmcid(raw: str) -> str | None:
        """Extract the exact PMC article ID without interpreting article content."""
        try:
            root = ET.fromstring(raw)
        except ET.ParseError:
            return None
        for article_id in root.findall(".//ArticleId"):
            if str(article_id.attrib.get("IdType", "")).casefold() != "pmc":
                continue
            value = (article_id.text or "").strip()
            if re.fullmatch(r"PMC\d+", value, re.IGNORECASE):
                return value.upper()
        return None

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

    @staticmethod
    def _openalex_identifier(identifier: str) -> str:
        value = identifier.strip()
        value = re.sub(r"^https?://openalex\.org/", "", value, flags=re.IGNORECASE)
        if re.fullmatch(r"W\d+", value, re.IGNORECASE):
            return value.upper()
        doi = re.sub(r"^(?:https?://(?:dx\.)?doi\.org/|doi:)", "", value, flags=re.IGNORECASE)
        if re.fullmatch(r"10\.\d{4,9}/[^\s?#]+", doi):
            return "https://doi.org/" + doi
        raise ValueError("OpenAlex identifier must be a work ID (W...) or DOI")

    @staticmethod
    def _zenodo_identifier(identifier: str) -> str:
        value = identifier.strip()
        value = re.sub(r"^https?://zenodo\.org/records?/", "", value, flags=re.IGNORECASE).rstrip("/")
        value = re.sub(r"^(?:https?://doi\.org/|doi:)?10\.5281/zenodo\.", "", value, flags=re.IGNORECASE)
        if not re.fullmatch(r"\d+", value):
            raise ValueError("Zenodo identifier must be a record ID, record URL, or Zenodo DOI")
        return value

    @staticmethod
    def _openalex_record(item: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": item.get("id"), "doi": item.get("doi"),
            "title": item.get("title") or item.get("display_name"),
            "published": item.get("publication_date"), "type": item.get("type"),
            "authors": [row.get("author", {}).get("display_name") for row in item.get("authorships", [])],
            "cited_by_count": item.get("cited_by_count"),
            "referenced_works": item.get("referenced_works", []),
            "related_works": item.get("related_works", []),
            "open_access": item.get("open_access"),
            "locations": item.get("locations", []),
            "ids": item.get("ids", {}), "is_retracted": item.get("is_retracted"),
            "abstract_inverted_index": item.get("abstract_inverted_index"),
            "content_level": "metadata_only", "has_full_text": False,
            "url": item.get("id"),
        }

    @staticmethod
    def _zenodo_record(item: dict[str, Any]) -> dict[str, Any]:
        metadata = item.get("metadata", {})
        files = item.get("files", [])
        # Invenio responses may expose a keyed entries map; preserve both APIs.
        if isinstance(files, dict):
            files = [{"key": key, **value} for key, value in files.get("entries", {}).items()]
        return {
            "id": str(item.get("id", "")), "doi": item.get("doi") or metadata.get("doi"),
            "title": metadata.get("title"), "published": metadata.get("publication_date"),
            "description": metadata.get("description"),
            "authors": [row.get("name") for row in metadata.get("creators", [])],
            "resource_type": metadata.get("resource_type") or metadata.get("upload_type"),
            "license": metadata.get("license") or metadata.get("rights"),
            "access_right": metadata.get("access_right") or item.get("access"),
            "related_identifiers": metadata.get("related_identifiers", []),
            "version": metadata.get("version"),
            "files": [{"name": row.get("key") or row.get("filename"), "size_bytes": row.get("size"), "checksum": row.get("checksum"), "links": row.get("links", {})} for row in files],
            "content_level": "metadata_only", "has_full_text": False,
            "url": item.get("links", {}).get("html") or item.get("links", {}).get("self_html"),
        }

    def _search_openalex(self, query: str, limit: int, cursor: str | None) -> dict[str, Any]:
        url = SOURCES["openalex"]["base_url"] + "?" + urllib.parse.urlencode({"search": query, "per_page": limit, "cursor": cursor or "*"})
        payload = self._request(self.json_transport, url)
        results = [self._openalex_record(item) for item in payload.get("results", [])]
        meta = payload.get("meta", {})
        candidate = meta.get("next_cursor")
        next_cursor = candidate if results and candidate and candidate != (cursor or "*") else None
        return {"source": "openalex", "query": query, **self._page_fields(results, total_count=meta.get("count"), next_cursor=next_cursor), "search_url": url, "usage": {key: meta[key] for key in ("cost_usd", "credits_used", "rate_limit_remaining") if key in meta}, "authentication_mode": "anonymous", "limitation": "One bounded page per request; no automatic crawl, API key, or paid fallback."}

    def _search_zenodo(self, query: str, limit: int, cursor: str | None) -> dict[str, Any]:
        try:
            page = int(cursor or "1")
        except ValueError as exc:
            raise ValueError("Zenodo cursor must be a positive integer page") from exc
        if page < 1:
            raise ValueError("Zenodo cursor must be a positive integer page")
        url = SOURCES["zenodo"]["base_url"] + "?" + urllib.parse.urlencode({"q": query, "size": limit, "page": page, "sort": "bestmatch"})
        payload = self._request(self.json_transport, url)
        hits = payload.get("hits", {})
        results = [self._zenodo_record(item) for item in hits.get("hits", [])]
        total = hits.get("total")
        relation = total.get("relation") if isinstance(total, dict) else "eq"
        total = total.get("value") if isinstance(total, dict) else total
        exact_total = total if relation == "eq" else None
        has_next = bool(payload.get("links", {}).get("next")) or (isinstance(total, int) and page * limit < total)
        next_cursor = str(page + 1) if results and has_next else None
        return {"source": "zenodo", "query": query, **self._page_fields(results, total_count=exact_total, next_cursor=next_cursor), "search_url": url, "total_count_lower_bound": total if relation != "eq" else None, "limitation": "Published-record metadata and file manifests only; no files downloaded."}


__all__ = ["SOURCES", "ScientificKnowledgeClient"]
