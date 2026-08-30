from __future__ import annotations

import unittest
import urllib.error
import urllib.parse

from frontier_research_harness.adapters.scientific_knowledge import ScientificKnowledgeClient


class ScientificKnowledgeTests(unittest.TestCase):
    def test_sources_are_direct_and_explicit(self):
        sources = ScientificKnowledgeClient().list_sources()["sources"]
        self.assertEqual({item["id"] for item in sources}, {"pubmed", "europe_pmc", "crossref", "clinical_trials", "nsca"})

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


if __name__ == "__main__":
    unittest.main()
