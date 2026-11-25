from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from training_records import append_record, read_record


class TrainingRecordsTests(unittest.TestCase):
    def setUp(self):
        self.directory = self.enterContext(TemporaryDirectory())
        self.enterContext(patch("training_records.settings", return_value={"records": self.directory}))

    def test_initial_read_has_no_filesystem_side_effect(self):
        self.assertEqual(read_record(), {"records": [], "next_before_id": None})
        self.assertEqual(list(Path(self.directory).iterdir()), [])

    def test_prediction_adoption_observation_and_correction_survive_reopen(self):
        prediction = append_record("rhythm", "prediction", "Improve on a novel pattern.", "request-p")
        plan = append_record("rhythm", "plan", "Use two separate patterns.", "request-plan", refs=[prediction["id"]])
        append_record("rhythm", "adoption", "User selected this plan.", "request-adopt", refs=[plan["id"]])
        obs = append_record("rhythm", "actual", "Novel pattern score 8/10.", "request-o",
                            refs=[plan["id"]], occurred_on="2026-11-21")
        updated = append_record("rhythm", "actual", "The 8/10 pattern had been practiced.", "request-fix",
                                corrects=obs["id"], refs=[plan["id"]], occurred_on="2026-11-21")
        review = append_record("rhythm", "review", "Hold transfer judgment.", "request-r",
                               refs=[prediction["id"], updated["id"]])

        original = read_record(record_id=prediction["id"])["records"][0]
        self.assertEqual(original, prediction)
        original_obs = read_record(record_id=obs["id"])["records"][0]
        self.assertEqual(original_obs["body"], "Novel pattern score 8/10.")
        self.assertEqual(original_obs["corrected_by"], updated["id"])
        first = read_record(topic="rhythm", limit=2)
        second = read_record(topic="rhythm", before_id=first["next_before_id"])
        all_ids = [r["id"] for r in first["records"] + second["records"]]
        self.assertEqual(all_ids, list(range(review["id"], 0, -1)))
        self.assertEqual(read_record()["records"][0]["topic"], "rhythm")

    def test_partial_failure_and_conflict(self):
        with self.assertRaises(ValueError):
            append_record("rhythm", "adoption", "Selected.", "req", refs=[93])
        self.assertEqual(read_record()["records"], [])
        plan = append_record("rhythm", "plan", "Proposal.", "req")
        with self.assertRaises(ValueError):
            append_record("rhythm", "plan", "Changed.", "req")
        with self.assertRaises(ValueError):
            append_record("other", "adoption", "Selected.", "other", refs=[plan["id"]])
        with self.assertRaises(ValueError):
            append_record("rhythm", "plan", "Updated", "bad-date", occurred_on="2026-02-31")
        self.assertEqual(len(read_record()["records"]), 1)

    def test_concurrent_requests_are_idempotent_and_no_correction_is_lost(self):
        def write(_):
            return append_record("rhythm", "actual", "6/10", "same")["id"]
        with ThreadPoolExecutor(max_workers=4) as pool:
            ids = list(pool.map(write, range(8)))
        self.assertEqual(len(set(ids)), 1)
        amended = append_record("rhythm", "actual", "7/10", "fix", corrects=ids[0])
        replay = append_record("rhythm", "actual", "7/10", "fix", corrects=ids[0])
        self.assertEqual(replay, amended)
        with self.assertRaises(ValueError):
            append_record("rhythm", "actual", "8/10", "lost", corrects=ids[0])
        self.assertEqual(len(read_record()["records"]), 2)


if __name__ == "__main__":
    unittest.main()
