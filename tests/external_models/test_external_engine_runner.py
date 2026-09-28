"""Tests for the external engine process boundary."""
import tempfile
import unittest
import os
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from frontier_research_harness.external_models.external_engine_federation import (
    ConnectionStatus, ExternalComponent, FederationInventory, FederationRole,
)
from frontier_research_harness.external_models.external_engine_runner import (
    ExternalEngineError, ExternalEngineJob, ExternalEngineRunner,
)


class ExternalEngineRunnerTests(unittest.TestCase):
    def test_timeout_and_missing_output_preserve_available_process_diagnostics(self):
        import subprocess

        component = ExternalComponent(
            component_id="pulse", name="Pulse", layer="physiology",
            role=FederationRole.EXECUTION_ENGINE, status=ConnectionStatus.READY,
            runtime_path="registered.exe",
        )
        inventory = FederationInventory(components=(component,), executable_component_ids=("pulse",), ready_for_execution=True, blocking_component_ids=())
        for outcome in (
            subprocess.TimeoutExpired("registered.exe", 1, output=b"partial output", stderr=b"partial error"),
            subprocess.CompletedProcess([], 0, b"completed but missing artifact", b""),
        ):
            with self.subTest(outcome=type(outcome).__name__), tempfile.TemporaryDirectory() as directory, patch(
                "frontier_research_harness.external_models.external_engine_runner.external_federation_inventory", return_value=inventory
            ), patch("frontier_research_harness.external_models.external_engine_runner.subprocess.run") as run:
                if isinstance(outcome, Exception):
                    run.side_effect = outcome
                else:
                    run.return_value = outcome
                with self.assertRaises(ExternalEngineError) as caught:
                    ExternalEngineRunner().run(ExternalEngineJob(
                        component_id="pulse", timeout_seconds=1, expected_output_artifacts=("missing.dat",),
                    ), workspace_root=directory)
                receipt = caught.exception.receipt
                self.assertEqual(receipt.runtime_path, "registered.exe")
                if isinstance(outcome, Exception):
                    self.assertEqual(receipt.timeout_seconds, 1)
                    self.assertEqual(receipt.stdout, "partial output")
                    self.assertEqual(receipt.stderr, "partial error")
                else:
                    self.assertEqual(receipt.exit_code, 0)
                    self.assertEqual(receipt.stdout, "completed but missing artifact")

    def test_missing_runtime_never_falls_back_to_python_equations(self):
        component = ExternalComponent(component_id="pulse", name="Pulse", layer="physiology", role=FederationRole.EXECUTION_ENGINE, status=ConnectionStatus.RUNTIME_MISSING)
        inventory = FederationInventory(components=(component,), executable_component_ids=("pulse",), ready_for_execution=False, blocking_component_ids=("pulse",))
        with patch("frontier_research_harness.external_models.external_engine_runner.external_federation_inventory", return_value=inventory):
            with self.assertRaisesRegex(RuntimeError, "not ready"):
                ExternalEngineRunner().run(ExternalEngineJob(component_id="pulse"))

    def test_only_registered_runtime_is_executed_without_shell(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "input.dat"; source.write_bytes(b"input")
            (root / "scenario.json").write_text("{}", encoding="utf-8")
            output = root / "output.dat"; output.write_bytes(b"output")
            component = ExternalComponent(component_id="pulse", name="Pulse", layer="physiology", role=FederationRole.EXECUTION_ENGINE, status=ConnectionStatus.READY, runtime_path="registered.exe")
            inventory = FederationInventory(components=(component,), executable_component_ids=("pulse",), ready_for_execution=True, blocking_component_ids=())
            completed = subprocess_result = __import__("subprocess").CompletedProcess([], 0, "ok", "")
            with patch("frontier_research_harness.external_models.external_engine_runner.external_federation_inventory", return_value=inventory), patch("frontier_research_harness.external_models.external_engine_runner.subprocess.run", return_value=completed) as run:
                receipt = ExternalEngineRunner().run(ExternalEngineJob(component_id="pulse", arguments=("scenario.json",), input_artifacts=("input.dat", "scenario.json"), expected_output_artifacts=("output.dat",)), workspace_root=root)
            self.assertEqual(receipt.stdout, "ok")
            self.assertEqual(receipt.inputs[0].sha256, "c96c6d5be8d08a12e7b5cdc1b207fa6b2430974c86803d8891675e76fd992c20")
            self.assertFalse(run.call_args.kwargs["shell"])
            self.assertEqual(run.call_args.args[0][0], "registered.exe")
            self.assertEqual(run.call_args.args[0][1], str((root / "scenario.json").resolve()))

    def test_registered_native_runtime_does_not_inherit_python_environment(self):
        component = ExternalComponent(
            component_id="circadapt", name="CircAdapt", layer="circulation",
            role=FederationRole.EXECUTION_ENGINE, status=ConnectionStatus.READY,
            runtime_path="registered-python.exe",
        )
        inventory = FederationInventory(
            components=(component,), executable_component_ids=("circadapt",),
            ready_for_execution=True, blocking_component_ids=(),
        )
        completed = __import__("subprocess").CompletedProcess([], 0, "ok", "")
        contaminated = {
            "PATH": os.environ.get("PATH", ""),
            "PYTHONPATH": "cp313-site-packages",
            "PYTHONHOME": "project-python",
            "VIRTUAL_ENV": "project-venv",
            "CONDA_PREFIX": "project-conda",
        }
        with tempfile.TemporaryDirectory() as directory, patch.dict(
            os.environ, contaminated, clear=True
        ), patch(
            "frontier_research_harness.external_models.external_engine_runner.external_federation_inventory",
            return_value=inventory,
        ), patch(
            "frontier_research_harness.external_models.external_engine_runner.subprocess.run",
            return_value=completed,
        ) as run:
            ExternalEngineRunner().run(
                ExternalEngineJob(component_id="circadapt"), workspace_root=directory
            )
        environment = run.call_args.kwargs["env"]
        self.assertIn("PATH", environment)
        self.assertNotIn("PYTHONPATH", environment)
        self.assertNotIn("PYTHONHOME", environment)
        self.assertNotIn("VIRTUAL_ENV", environment)
        self.assertNotIn("CONDA_PREFIX", environment)

    def test_failure_reports_stdout_when_native_engine_uses_it_for_diagnostics(self):
        component = ExternalComponent(
            component_id="pulse", name="Pulse", layer="physiology",
            role=FederationRole.EXECUTION_ENGINE, status=ConnectionStatus.READY,
            runtime_path="registered.exe",
        )
        inventory = FederationInventory(
            components=(component,), executable_component_ids=("pulse",),
            ready_for_execution=True, blocking_component_ids=(),
        )
        completed = __import__("subprocess").CompletedProcess(
            [], 1, b"scenario parse failed", b""
        )
        with tempfile.TemporaryDirectory() as directory, patch(
            "frontier_research_harness.external_models.external_engine_runner.external_federation_inventory",
            return_value=inventory,
        ), patch(
            "frontier_research_harness.external_models.external_engine_runner.subprocess.run",
            return_value=completed,
        ):
            with self.assertRaisesRegex(RuntimeError, "scenario parse failed"):
                ExternalEngineRunner().run(
                    ExternalEngineJob(component_id="pulse"), workspace_root=directory
                )

    def test_python_module_registration_uses_current_interpreter_and_moco_plugin_path(self):
        component = ExternalComponent(
            component_id="moco", name="Moco", layer="mechanics",
            role=FederationRole.EXECUTION_ENGINE, status=ConnectionStatus.READY,
            runtime_path="python:opensim",
        )
        inventory = FederationInventory(
            components=(component,), executable_component_ids=("moco",),
            ready_for_execution=True, blocking_component_ids=(),
        )
        completed = __import__("subprocess").CompletedProcess([], 0, "ok", "")
        with tempfile.TemporaryDirectory() as directory, patch(
            "frontier_research_harness.external_models.external_engine_runner.external_federation_inventory",
            return_value=inventory,
        ), patch(
            "frontier_research_harness.external_models.external_engine_runner.find_spec",
            return_value=SimpleNamespace(origin=str(Path(directory) / "opensim" / "__init__.py")),
        ), patch(
            "frontier_research_harness.external_models.external_engine_runner.subprocess.run",
            return_value=completed,
        ) as run:
            ExternalEngineRunner().run(
                ExternalEngineJob(component_id="moco", arguments=("driver.py",)),
                workspace_root=directory,
            )
        self.assertTrue(run.call_args.args[0][0].lower().endswith("python.exe") or run.call_args.args[0][0].lower().endswith("python"))
        self.assertEqual(run.call_args.args[0][1], "driver.py")
        self.assertTrue(run.call_args.kwargs["env"]["CASADIPATH"].endswith("opensim"))

    def test_native_output_uses_windows_code_page_when_utf8_decode_fails(self):
        component = ExternalComponent(
            component_id="pulse", name="Pulse", layer="physiology",
            role=FederationRole.EXECUTION_ENGINE, status=ConnectionStatus.READY,
            runtime_path="registered.exe",
        )
        inventory = FederationInventory(
            components=(component,), executable_component_ids=("pulse",),
            ready_for_execution=True, blocking_component_ids=(),
        )
        completed = __import__("subprocess").CompletedProcess(
            [], 0, "계산 완료".encode("cp949"), b""
        )
        with tempfile.TemporaryDirectory() as directory, patch(
            "frontier_research_harness.external_models.external_engine_runner.external_federation_inventory",
            return_value=inventory,
        ), patch(
            "frontier_research_harness.external_models.external_engine_runner.locale.getencoding",
            return_value="cp949",
        ), patch(
            "frontier_research_harness.external_models.external_engine_runner.subprocess.run",
            return_value=completed,
        ) as run:
            receipt = ExternalEngineRunner().run(
                ExternalEngineJob(component_id="pulse"), workspace_root=directory
            )
        self.assertEqual(receipt.stdout, "계산 완료")
        self.assertFalse(run.call_args.kwargs["text"])


if __name__ == "__main__":
    unittest.main()
