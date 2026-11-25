"""Behavioral checks for public citation routing and bounded source reads."""
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import training_literature as lit


class PublicLiterature(unittest.TestCase):
    def test_discovery_and_reopening_body(self):
        result = {"resultList": {"result": [{"title": "A", "doi": "10.1/a",
                                             "pmid": "1", "pmcid": "PMC9"}]}}
        xml = """<article><body><sec><title>Results</title><p>Measured change.</p>
        <table-wrap><label>Table 1</label><table><tr><th>Distance</th><th>Unit</th></tr>
        <tr><td>5</td><td>cm</td></tr></table><table-wrap-foot>Mean</table-wrap-foot>
        </table-wrap></sec></body></article>"""
        with patch.object(lit, "fetch", side_effect=[json.dumps(result), xml, xml]) as calls:
            row = lit.search_papers("balance")["results"][0]
            self.assertEqual(row["read_ids"], ["PMC9", "PMID:1"])
            first = lit.read_source(row["read_ids"][0], max_chars=13)
            last = lit.read_source("PMC9", offset=first["next_offset"])
        self.assertEqual(first["scope"], "full_text_body")
        self.assertEqual(first["sha256"], last["sha256"])
        self.assertIn("5 | cm\nMean", first["excerpt"] + last["excerpt"])
        self.assertEqual(last["total_chars"], len(first["excerpt"] + last["excerpt"]))
        self.assertIsNone(last["next_offset"])
        self.assertIn("table-wrap", last["locators"][-1]["locator"])
        self.assertEqual(calls.call_args_list[-1].args, ("pmc-xml", "PMC9", 1))

    def test_abstract_and_unavailable_abstract(self):
        xml = ('<PubmedArticleSet><PubmedArticle><MedlineCitation><PMID>2</PMID><Article>'
               '<ArticleTitle>T</ArticleTitle><Abstract><AbstractText Label="METHODS">group A'
               '</AbstractText></Abstract></Article></MedlineCitation></PubmedArticle></PubmedArticleSet>')
        with patch.object(lit, "fetch", return_value=xml):
            value = lit.read_source("pmid:2")
            self.assertEqual(value["scope"], "abstract")
            self.assertIn("METHODS", value["locators"][0]["locator"])
            with self.assertRaises(ValueError):
                lit.read_source("PMID:99")
        with patch.object(lit, "fetch", return_value=xml.replace("AbstractText", "Unavailable")):
            self.assertEqual(lit.read_source("PMID:2")["scope"], "metadata_only")

    def test_public_provider_normalization(self):
        raw = {
            "pubmed": {"esearchresult": {"idlist": ["543"]}},
            "openalex": {"results": [{"display_name":"A", "id":"https://openalex.org/W2", "ids":
                                      {"pmid":"https://pubmed.ncbi.nlm.nih.gov/543/"}}]},
            "semantic-scholar": {"data": [{"title":"A","paperId":"s2","externalIds":{"PubMed":"543"}}]},
            "datacite": {"data": [{"id":"10.0/z","attributes":{"titles":[{"title":"A"}]}}]},
            "sportrxiv": {"message":{"items":[{"title":["A"],"DOI":"10.0/z"}]}},
            "retractions": {"message":{"items":[{"DOI":"10.0/z","update-to":[{"DOI":"10.0/x","type":"retraction","source":"publisher"}]}]}},
            "arxiv-feed": [{"title":"A","url":"https://arxiv.org/abs/1234.56789"}],
            "jstage": '<feed xmlns="urn:a"><entry><title>A</title><id>entry1</id><link href="https://example.org"/></entry></feed>',
        }
        for provider, body in raw.items():
            with self.subTest(provider=provider), patch.object(lit,"fetch", return_value=body if isinstance(body,str) else json.dumps(body)):
                result=lit.search_papers("q-bio.QM",provider)["results"][0]
                self.assertTrue(result["citation_id"])
                if provider == "retractions":
                    self.assertEqual(result["updates"][0]["doi"], "10.0/x")

    def test_unapproved_targets_never_fetch(self):
        with patch.object(lit, "fetch") as call:
            for provider in ("youtube", "zotero", "feed", "nonsense"):
                with self.assertRaises(ValueError):
                    lit.search_papers("hi", provider)
            with self.assertRaises(ValueError):
                lit.search_papers("https://example.org", "arxiv-feed")
            with self.assertRaises(ValueError):
                lit.read_source("https://example.org")
            with self.assertRaises(ValueError):
                lit.search_papers("q", limit=999)
            call.assert_not_called()

    def test_network_error_does_not_emit_urls_or_api_credentials(self):
        with patch.object(lit, "fetch", side_effect=lit.requests.Timeout("URL-with-secret")):
            with self.assertRaisesRegex(ValueError, "^pubmed: Timeout$"):
                lit.search_papers("term", "pubmed")
