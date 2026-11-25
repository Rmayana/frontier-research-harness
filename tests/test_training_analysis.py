"""Synthetic tests for local-only measurement and media tools."""
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from training_analysis import inspect_video, read_activity, run_analysis


class TrainingAnalysisTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.inbox = self.root / "inbox"
        self.inbox.mkdir()
        self.runtime = {"records": str(self.root)}
        mocked = patch("training_analysis.settings", return_value=self.runtime)
        mocked.start()
        self.addCleanup(mocked.stop)

    def test_csv_paging_preserves_zero_missing_and_offsets(self):
        (self.inbox / "test.csv").write_text("x,condition\n0,\n2,a\n", encoding="utf-8-sig")
        first = read_activity("test.csv", limit=1)
        self.assertEqual(first["rows"], [{"x": "0", "condition": ""}])
        self.assertEqual(first["next_offset"], 1)
        last = read_activity("test.csv", offset=1, limit=1)
        self.assertEqual(last["rows"], [{"x": "2", "condition": "a"}])
        self.assertIsNone(last["next_offset"])

    def test_only_supported_inbox_inputs(self):
        (self.root / "outside.csv").write_text("private\n1\n")
        for name in ("../outside.csv", str(self.root / "outside.csv"), "file.csv:secret"):
            with self.subTest(name=name), self.assertRaises(ValueError):
                read_activity(name)
        (self.inbox / "malformed.csv").write_text("x,x\n2,3\n")
        with self.assertRaises(ValueError):
            read_activity("malformed.csv")
        with self.assertRaises(ValueError):
            inspect_video("https://example.org/external.mp4")

    def test_fit_record(self):
        from garmin_fit_sdk import Encoder

        encoder = Encoder()
        encoder.write_mesg({"mesg_num": 20, "heart_rate": 99})
        (self.inbox / "synth.fit").write_bytes(encoder.close())
        self.assertEqual(read_activity("synth.fit")["rows"][0]["heart_rate"], 99)

    def test_calculation_and_paired_constraints(self):
        comparison = run_analysis([0, 2], [3, 5], "points", paired=True)
        self.assertEqual(comparison["mean_change"], 3)
        self.assertEqual(comparison["within_pair_change"]["sample_sd"], 0)
        for first, second in (([], [2.0]), ([1.0], [1.0, 2.0]), ([float("nan")], [1.0])):
            with self.assertRaises(ValueError):
                run_analysis(first, second, "points", paired=True)

    def test_frame_and_duration(self):
        host = Path.home() / "AppData/Local/FrontierTraining/local-tools.json"
        paths = json.loads(host.read_text(encoding="utf-8-sig")) if host.is_file() else {}
        for name in ("ffmpeg", "ffprobe"):
            executable = paths.get(name) or shutil.which(name)
            if not executable:
                self.skipTest(f"{name} required for integration test")
            self.runtime[name] = executable
        subprocess.run([self.runtime["ffmpeg"], "-v", "error", "-nostdin", "-f", "lavfi",
                        "-i", "color=size=64x80:duration=1", str(self.inbox / "test.mp4")],
                       check=True, timeout=20)
        self.assertEqual(inspect_video("test.mp4")["height"], 80)
        self.assertTrue(inspect_video("test.mp4", 0.2)["frame_jpeg"].startswith(b"\xff\xd8"))
        with self.assertRaises(ValueError):
            inspect_video("test.mp4", 10)
