"""Tests for fail-closed external-model discovery."""
from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from frontier_research_harness.external_models.external_engine_federation import (
    ConnectionStatus,
    ExternalFederationNotReadyError,
    external_federation_inventory,
    require_external_federation_ready,
)


class ExternalFederationTests(unittest.TestCase):
    def test_registered_runtime_requires_exact_hash(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            runtime = root / "runtime.exe"
            runtime.write_bytes(b"registered-runtime")
            root.joinpath(".external-engine-runtimes.json").write_text(
                json.dumps({
                    "schema_version": "external-engine-runtime-manifest-v1",
                    "runtimes": [{
                        "component_id": "pulse",
                        "path": "runtime.exe",
                        "sha256": hashlib.sha256(runtime.read_bytes()).hexdigest(),
                    }],
                }),
                encoding="utf-8",
            )
            inventory = external_federation_inventory(root)
            pulse = next(
                item for item in inventory.components
                if item.component_id == "pulse"
            )
            self.assertEqual(pulse.status, ConnectionStatus.RUNTIME_UNVERIFIED)
            self.assertEqual(Path(pulse.runtime_path), runtime)

    def test_registered_runtime_hash_mismatch_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            root.joinpath("runtime.exe").write_bytes(b"tampered")
            root.joinpath(".external-engine-runtimes.json").write_text(
                json.dumps({
                    "schema_version": "external-engine-runtime-manifest-v1",
                    "runtimes": [{
                        "component_id": "pulse",
                        "path": "runtime.exe",
                        "sha256": "0" * 64,
                    }],
                }),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "hash mismatch"):
                external_federation_inventory(root)

    def test_missing_registered_runtime_does_not_fall_back(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            legacy = root / ".scratch/pulse-ascii/install/bin"
            legacy.mkdir(parents=True)
            legacy.joinpath("PulseScenarioDriver.exe").write_bytes(b"legacy")
            root.joinpath(".external-engine-runtimes.json").write_text(
                json.dumps({
                    "schema_version": "external-engine-runtime-manifest-v1",
                    "runtimes": [{
                        "component_id": "pulse",
                        "path": "registered/missing.exe",
                        "sha256": hashlib.sha256(b"expected").hexdigest(),
                    }],
                }),
                encoding="utf-8",
            )
            inventory = external_federation_inventory(root)
            pulse = next(
                item for item in inventory.components
                if item.component_id == "pulse"
            )
            self.assertIsNone(pulse.runtime_path)
            self.assertEqual(pulse.status, ConnectionStatus.RUNTIME_MISSING)

    def test_source_checkout_never_counts_as_executable_runtime(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); root.joinpath("vendor/opensim-core").mkdir(parents=True)
            inventory=external_federation_inventory(root)
            opensim=next(x for x in inventory.components if x.component_id=="opensim")
            self.assertIn(
                opensim.status,
                {
                    ConnectionStatus.SOURCE_ONLY,
                    ConnectionStatus.RUNTIME_UNVERIFIED,
                    ConnectionStatus.READY,
                },
            )
            if opensim.runtime_path != "python:opensim":
                self.assertEqual(opensim.status,ConnectionStatus.SOURCE_ONLY)

    def test_reference_projects_are_not_execution_engines(self):
        inventory=external_federation_inventory()
        self.assertNotIn("vmh", inventory.executable_component_ids)
        self.assertNotIn("edith_vht", inventory.executable_component_ids)
        self.assertNotIn("human_gem", inventory.executable_component_ids)

    def test_cobra_engine_and_human_gem_asset_remain_distinct(self):
        inventory = external_federation_inventory()
        cobra = next(x for x in inventory.components if x.component_id == "cobra")
        human_gem = next(x for x in inventory.components if x.component_id == "human_gem")
        self.assertEqual(cobra.status, ConnectionStatus.READY)
        self.assertEqual(cobra.runtime_path, "python:cobra")
        self.assertEqual(human_gem.status, ConnectionStatus.MODEL_ASSET_READY)
        self.assertIsNone(human_gem.runtime_path)

    def test_mobi_installation_does_not_claim_unverified_model_execution(self):
        inventory = external_federation_inventory()
        mobi = next(x for x in inventory.components if x.component_id == "mobi")
        self.assertEqual(mobi.status, ConnectionStatus.RUNTIME_UNVERIFIED)
        self.assertTrue(mobi.runtime_path.endswith("MoBi.exe"))
        self.assertIn("no successful model smoke-test receipt", mobi.blockers[0])

    def test_mitocore_and_mechanistic_qsp_are_distinct_assets(self):
        inventory = external_federation_inventory()
        mitocore = next(x for x in inventory.components if x.component_id == "mitocore")
        qsp = next(x for x in inventory.components if x.component_id == "mitochondria_qsp")
        self.assertEqual(mitocore.status, ConnectionStatus.MODEL_ASSET_READY)
        self.assertIsNone(mitocore.runtime_path)
        self.assertEqual(qsp.status, ConnectionStatus.MODEL_ASSET_READY)
        self.assertIsNotNone(qsp.source_path)
        self.assertTrue(qsp.runtime_path.endswith("octave-cli.exe"))
        self.assertNotIn("mitocore", inventory.executable_component_ids)
        self.assertNotIn("mitochondria_qsp", inventory.executable_component_ids)

    def test_missing_external_federation_fails_closed(self):
        inventory=external_federation_inventory()
        if not inventory.ready_for_execution:
            with self.assertRaises(ExternalFederationNotReadyError):
                require_external_federation_ready()

    def test_new_local_remote_and_account_bound_components_are_explicit(self):
        inventory = external_federation_inventory()
        by_id = {item.component_id: item for item in inventory.components}
        for component_id in ("myosuite", "physicell", "simvascular_lite", "libcellml", "sparc"):
            self.assertEqual(by_id[component_id].status, ConnectionStatus.READY)
            self.assertIsNotNone(by_id[component_id].runtime_path)
        self.assertEqual(by_id["opencap"].status, ConnectionStatus.SOURCE_ONLY)
        self.assertIsNotNone(by_id["opencap"].source_path)
        self.assertEqual(by_id["harvey_harvetta"].status, ConnectionStatus.MODEL_ASSET_REQUIRED)
        self.assertEqual(by_id["sim4life"].status, ConnectionStatus.LICENSE_REQUIRED)


if __name__ == "__main__":
    unittest.main()
