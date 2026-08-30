from __future__ import annotations

import unittest

from pydantic import ValidationError

from frontier_research_harness.footage_contracts import FootageObservation


class FootageContractTests(unittest.TestCase):
    def test_observation_becomes_primary_source_evidence(self):
        observation = FootageObservation(
            source="official fight footage", reference_url="https://example.test/fight",
            title="Beterbiev pressure sequence", athlete="Artur Beterbiev",
            opponent_or_context="round 3", start_seconds=120, end_seconds=126,
            observed_actions=("cuts the exit with the lead foot",),
            situational_conditions=("opponent circles clockwise",), repeated_pattern=True,
            derived_drills=("exit-cutting constraint sparring",),
            applicability="Pressure and ring-cutting component of the technical goal.",
            limitations=("One camera angle.",),
        )
        record = observation.evidence_record()
        self.assertEqual(record["classification"], "EXTERNAL_PRIMARY_SOURCE")
        self.assertEqual(record["content_level"], "primary_source_observation")
        self.assertIn("120.000-126.000s", record["retained_claims"][0])

    def test_timestamp_order_fails_closed(self):
        with self.assertRaisesRegex(ValidationError, "end_seconds"):
            FootageObservation(
                source="video", reference_url="https://example.test", title="clip",
                athlete="athlete", opponent_or_context="sparring", start_seconds=3,
                end_seconds=2, observed_actions=("jab",), situational_conditions=("open stance",),
                applicability="technique", limitations=("short clip",),
            )


if __name__ == "__main__":
    unittest.main()
