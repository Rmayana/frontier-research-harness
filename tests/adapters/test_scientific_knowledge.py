from __future__ import annotations

import unittest
import urllib.error
import urllib.parse

from frontier_research_harness.adapters.scientific_knowledge import ScientificKnowledgeClient


class ScientificKnowledgeTests(unittest.TestCase):
    def test_sources_are_direct_and_explicit(self):
        sources = ScientificKnowledgeClient().list_sources()["sources"]
        self.assertEqual({item["id"] for item in sources}, {"pubmed", "europe_pmc", "crossref", "clinical_trials", "nsca", "openalex", "zenodo"})

    def test_pubmed_search_normalizes_summary(self):
        def transport(url: str):
            if "esearch" in url:
                return {"esearchresult": {"idlist": ["123"]}}
            return {"result": {"123": {"title": "Training study", "authors": [{"name": "A Author"}], "fulljournalname": "Journal", "pubdate": "2026", "articleids": [{"idtype": "doi", "value": "10.1/test"}]}}}
        result = ScientificKnowledgeClient(json_transport=transport).search("pubmed", "training", 5)
        self.assertEqual(result["results"][0]["doi"], "10.1/test")

    def test_pubmed_search_exposes_count_and_next_cursor(self):
        urls = []
        def transport(url: str):
            urls.append(url)
            if "esearch" in url:
                return {"esearchresult": {"count": "120", "idlist": ["123", "124"]}}
            return {"result": {pmid: {"title": pmid} for pmid in ("123", "124")}}
        result = ScientificKnowledgeClient(json_transport=transport).search(
            "pubmed", "training", 2, cursor="50"
        )
        query = urllib.parse.parse_qs(urllib.parse.urlparse(urls[0]).query)
        self.assertEqual(query["retstart"], ["50"])
        self.assertEqual(result["total_count"], 120)
        self.assertEqual(result["returned_count"], 2)
        self.assertEqual(result["next_cursor"], "52")
        self.assertTrue(result["more_available"])

    def test_transient_transport_errors_are_retried(self):
        attempts = []
        delays = []
        def transport(_url: str):
            attempts.append(1)
            if len(attempts) < 3:
                raise urllib.error.URLError("temporary")
            return {"esearchresult": {"count": "0", "idlist": []}}
        result = ScientificKnowledgeClient(
            json_transport=transport,
            sleeper=delays.append,
        ).search("pubmed", "training")
        self.assertEqual(result["returned_count"], 0)
        self.assertEqual(len(attempts), 3)
        self.assertEqual(delays, [0.25, 0.5])

    def test_europe_pmc_and_crossref_are_not_quality_routers(self):
        europe = ScientificKnowledgeClient(json_transport=lambda _: {"resultList": {"result": [{"id": "1", "title": "Preprint", "source": "PPR"}]}}).search("europe_pmc", "exercise")
        crossref = ScientificKnowledgeClient(json_transport=lambda _: {"message": {"items": [{"DOI": "10.1/x", "title": ["Paper"]}]}}).search("crossref", "nutrition")
        self.assertEqual(europe["results"][0]["title"], "Preprint")
        self.assertEqual(crossref["results"][0]["doi"], "10.1/x")
        self.assertNotIn("quality_score", europe)

    def test_clinical_trials_search_normalizes_registration(self):
        payload = {"studies": [{"hasResults": True, "protocolSection": {
            "identificationModule": {"nctId": "NCT1", "briefTitle": "Exercise trial"},
            "statusModule": {"overallStatus": "COMPLETED"},
            "designModule": {"studyType": "INTERVENTIONAL", "phases": ["NA"]},
        }}]}
        result = ScientificKnowledgeClient(json_transport=lambda _: payload).search("clinical_trials", "exercise")
        self.assertEqual(result["results"][0]["id"], "NCT1")
        self.assertTrue(result["results"][0]["has_results"])
        self.assertEqual(result["results"][0]["content_level"], "metadata_only")

    def test_europe_pmc_cursor_is_round_tripped(self):
        payload = {
            "hitCount": 100,
            "nextCursorMark": "next-token",
            "resultList": {"result": [{"id": "1", "title": "Paper"}]},
        }
        result = ScientificKnowledgeClient(json_transport=lambda _: payload).search(
            "europe_pmc", "exercise", cursor="current-token"
        )
        self.assertEqual(result["next_cursor"], "next-token")
        self.assertEqual(result["total_count"], 100)

    def test_nsca_is_an_explicit_pubmed_journal_view(self):
        urls = []
        def transport(url: str):
            urls.append(url)
            if "esearch" in url:
                return {"esearchresult": {"idlist": []}}
            raise AssertionError(url)
        result = ScientificKnowledgeClient(json_transport=transport).search("nsca", "squat")
        self.assertEqual(result["source"], "nsca")
        self.assertIn('"J Strength Cond Res"[jour]', result["database_query"])
        self.assertTrue(urls)

    def test_pubmed_fetch_resolves_linked_pmc_full_text(self):
        urls = []

        def text_transport(url: str) -> str:
            urls.append(url)
            if "efetch.fcgi" in url:
                return (
                    "<PubmedArticleSet><PubmedArticle><PubmedData><ArticleIdList>"
                    '<ArticleId IdType="pubmed">123</ArticleId>'
                    '<ArticleId IdType="pmc">PMC456</ArticleId>'
                    "</ArticleIdList></PubmedData></PubmedArticle></PubmedArticleSet>"
                )
            if "PMC456/fullTextXML" in url:
                return "<article><body><p>Full text.</p></body></article>"
            raise AssertionError(url)

        result = ScientificKnowledgeClient(text_transport=text_transport).fetch(
            "pubmed", "123"
        )
        self.assertEqual(result["content_level"], "full_text")
        self.assertTrue(result["has_full_text"])
        self.assertEqual(result["pmcid"], "PMC456")
        self.assertEqual(result["source_record"]["content_level"], "record_with_abstract")
        self.assertEqual(len(urls), 2)

    def test_pubmed_fetch_keeps_abstract_when_pmc_resolution_fails(self):
        def text_transport(url: str) -> str:
            if "efetch.fcgi" in url:
                return '<ArticleIdList><ArticleId IdType="pmc">PMC456</ArticleId></ArticleIdList>'
            raise urllib.error.HTTPError(url, 404, "missing", {}, None)

        result = ScientificKnowledgeClient(
            text_transport=text_transport, max_attempts=1
        ).fetch("pubmed", "123")
        self.assertEqual(result["content_level"], "record_with_abstract")
        self.assertFalse(result["full_text_resolution"]["resolved"])

    def test_europe_pmc_resolves_typed_identifiers(self):
        for identifier, expected in (("PMC8505308", "PMCID:PMC8505308"), ("PMID:34390401", "EXT_ID:34390401 AND SRC:MED"), ("https://doi.org/10.1234/example", 'DOI:"10.1234/example"')):
            with self.subTest(identifier=identifier):
                urls = []
                def transport(url):
                    urls.append(url)
                    return {"resultList": {"result": [{"id": "123", "pmcid": "PMC456"}]}}
                result = ScientificKnowledgeClient(json_transport=transport, text_transport=lambda _: "<article><body><p>Full text.</p></body></article>").fetch("europe_pmc", identifier)
                self.assertEqual(urllib.parse.parse_qs(urllib.parse.urlparse(urls[0]).query)["query"], [expected])
                self.assertTrue(result["has_full_text"])

    def test_europe_pmc_failure_retains_abstract_and_does_not_claim_fulltext(self):
        def failed(url):
            raise urllib.error.HTTPError(url, 403, "restricted", {}, None)
        result = ScientificKnowledgeClient(json_transport=lambda _: {"resultList": {"result": [{"pmcid": "PMC456", "abstractText": "Abstract"}]}}, text_transport=failed).fetch("europe_pmc", "123")
        self.assertEqual(result["content_level"], "record_with_abstract")
        self.assertFalse(result["has_full_text"])
        self.assertEqual(result["raw"]["abstractText"], "Abstract")

    def test_europe_pmc_invalid_body_cannot_become_fulltext(self):
        for raw in ("<html><body>Error page</body></html>", "<article><front>Abstract</front></article>", "not XML"):
            with self.subTest(raw=raw):
                result = ScientificKnowledgeClient(json_transport=lambda _: {"resultList": {"result": [{"pmcid": "PMC456"}]}}, text_transport=lambda _: raw).fetch("europe_pmc", "123")
                self.assertEqual(result["content_level"], "metadata_only")
                self.assertFalse(result["has_full_text"])
                self.assertEqual(result["full_text_resolution"]["error_type"], "ValueError")

    def test_europe_pmc_absence_does_not_assert_no_fulltext_elsewhere(self):
        result = ScientificKnowledgeClient(json_transport=lambda _: {"resultList": {"result": []}}).fetch("europe_pmc", "123")
        self.assertIsNone(result["raw"])
        self.assertFalse(result["full_text_resolution"]["attempted"])
        self.assertIn("unknown", result["limitation"])
        with self.assertRaisesRegex(ValueError, "PMID, PMCID, or DOI"):
            ScientificKnowledgeClient().fetch("europe_pmc", '10.1234/x" OR title:foo')

    def test_openalex_preserves_citation_locations_and_usage_without_fulltext(self):
        urls = []
        def transport(url):
            urls.append(url)
            return {"meta": {"count": 25, "next_cursor": "next", "cost_usd": 0.0001}, "results": [{"id": "https://openalex.org/W1", "title": "Study", "referenced_works": ["https://openalex.org/W2"], "locations": [{"pdf_url": "https://example.org/paper.pdf"}], "open_access": {"is_oa": True}}]}
        result = ScientificKnowledgeClient(json_transport=transport).search("openalex", "exercise", 2)
        self.assertEqual(result["next_cursor"], "next")
        self.assertEqual(result["usage"]["cost_usd"], 0.0001)
        self.assertFalse(result["results"][0]["has_full_text"])
        self.assertEqual(result["results"][0]["referenced_works"], ["https://openalex.org/W2"])
        self.assertEqual(len(urls), 1)
        self.assertNotIn("api_key", urls[0])

    def test_openalex_fetch_doi_and_invalid_identifier(self):
        urls = []
        client = ScientificKnowledgeClient(json_transport=lambda url: urls.append(url) or {"id": "https://openalex.org/W1"})
        result = client.fetch("openalex", "doi:10.1234/example")
        self.assertIn("/works/https://doi.org/10.1234/example", urls[0])
        self.assertEqual(result["content_level"], "metadata_only")
        with self.assertRaises(ValueError):
            client.fetch("openalex", "https://untrusted.example/file")

    def test_zenodo_search_preserves_file_provenance_without_downloading(self):
        urls = []
        record = {"id": 123, "doi": "10.5281/zenodo.123", "metadata": {"title": "Measurements", "license": {"id": "cc-by-4.0"}, "resource_type": {"type": "dataset"}}, "files": [{"key": "data.csv", "size": 25, "checksum": "md5:abc", "links": {"self": "https://zenodo.org/files/data.csv"}}]}
        def transport(url):
            urls.append(url)
            return {"hits": {"total": {"value": 5, "relation": "eq"}, "hits": [record]}, "links": {"next": "https://untrusted.example/ignored"}}
        result = ScientificKnowledgeClient(json_transport=transport).search("zenodo", "force", 1)
        self.assertEqual(result["next_cursor"], "2")
        self.assertEqual(result["results"][0]["files"][0]["checksum"], "md5:abc")
        self.assertFalse(result["results"][0]["has_full_text"])
        self.assertEqual(len(urls), 1)
        self.assertEqual(ScientificKnowledgeClient(json_transport=lambda _: record).fetch("zenodo", "https://doi.org/10.5281/zenodo.123")["identifier"], "123")
        with self.assertRaises(ValueError):
            ScientificKnowledgeClient().search("zenodo", "force", cursor="https://untrusted.example")

    def test_zenodo_anonymous_page_limit_is_validated_without_transport(self):
        client = ScientificKnowledgeClient(json_transport=lambda _: self.fail("must not make a request"))
        with self.assertRaisesRegex(ValueError, "between 1 and 25"):
            client.search("zenodo", "force", 26)

    def test_zenodo_invenio_files_and_lower_bound_count(self):
        payload = {"hits": {"total": {"value": 10000, "relation": "gte"}, "hits": [{"id": "1", "metadata": {"title": "Data"}, "files": {"entries": {"data.csv": {"size": 25, "checksum": "md5:abc"}}}}]}}
        result = ScientificKnowledgeClient(json_transport=lambda _: payload).search("zenodo", "force", 1)
        self.assertIsNone(result["total_count"])
        self.assertEqual(result["total_count_lower_bound"], 10000)
        self.assertEqual(result["results"][0]["files"][0]["name"], "data.csv")
        self.assertEqual(result["next_cursor"], "2")

    def test_openalex_cursor_is_encoded_and_empty_page_stops(self):
        urls = []
        result = ScientificKnowledgeClient(json_transport=lambda url: urls.append(url) or {"meta": {"count": 0, "next_cursor": "repeated"}, "results": []}).search("openalex", "training", cursor="a+b/c==")
        self.assertEqual(urllib.parse.parse_qs(urllib.parse.urlparse(urls[0]).query)["cursor"], ["a+b/c=="])
        self.assertFalse(result["more_available"])


if __name__ == "__main__":
    unittest.main()
