"""Tests for the external scientific-model registry."""
import unittest

from pydantic import ValidationError

from frontier_research_harness.external_models.model_registry import (
    ModelRole,
    ModelRuntimeStatus,
    UnifiedModelRecord,
    unified_model_registry,
)


class UnifiedModelRegistryTests(unittest.TestCase):
    def test_live_federation_projects_into_one_registry(self):
        registry = unified_model_registry()
        ready = {record.model_id for record in registry.ready_models()}
        self.assertEqual(
            ready,
            {"opensim", "moco", "pulse", "febio", "circadapt", "hummod", "cobra", "pk_sim", "physicell", "myosuite", "simvascular_lite", "libcellml", "sparc"},
        )
        self.assertEqual(registry.get("hummod").role, ModelRole.VALIDATION_REFERENCE)
        self.assertEqual(registry.get("opensim").runtime_status, ModelRuntimeStatus.READY)
        self.assertEqual(registry.get("moco").runtime_status, ModelRuntimeStatus.READY)
        self.assertEqual(registry.get("pk_sim").runtime_status, ModelRuntimeStatus.READY)
        self.assertEqual(registry.get("anybody").runtime_status, ModelRuntimeStatus.LICENSE_REQUIRED)
        self.assertEqual(registry.get("mobi").runtime_status, ModelRuntimeStatus.RUNTIME_UNVERIFIED)
        self.assertEqual(registry.get("mobi").version, "12.3.136")
        self.assertEqual(registry.get("myosuite").version, "2.12.2")
        self.assertEqual(registry.get("physicell").version, "1.14.2")
        self.assertEqual(registry.get("simvascular_lite").role, ModelRole.ON_DEMAND)
        self.assertEqual(registry.get("libcellml").runtime_status, ModelRuntimeStatus.READY)
        self.assertEqual(registry.get("sparc").runtime_status, ModelRuntimeStatus.READY)
        self.assertEqual(registry.get("opencap").runtime_status, ModelRuntimeStatus.SOURCE_ONLY)
        self.assertEqual(registry.get("harvey_harvetta").runtime_status, ModelRuntimeStatus.MODEL_ASSET)
        self.assertEqual(registry.get("sim4life").runtime_status, ModelRuntimeStatus.LICENSE_REQUIRED)
        self.assertIsNone(registry.get("mobi").smoke_receipt_path)
        human_gem = registry.get("human_gem")
        self.assertEqual(human_gem.role, ModelRole.MODEL_ASSET)
        self.assertEqual(human_gem.runtime_status, ModelRuntimeStatus.MODEL_ASSET_READY)
        self.assertIsNotNone(human_gem.asset_receipt_path)
        self.assertIsNone(human_gem.runtime_path)
        self.assertEqual(human_gem.adapter_id, "passive.human_gem")
        mitocore = registry.get("mitocore")
        self.assertEqual(mitocore.version, "1.01")
        self.assertEqual(mitocore.role, ModelRole.MODEL_ASSET)
        self.assertEqual(mitocore.runtime_status, ModelRuntimeStatus.MODEL_ASSET_READY)
        self.assertEqual(mitocore.adapter_id, "passive.mitocore")
        qsp = registry.get("mitochondria_qsp")
        self.assertEqual(qsp.runtime_status, ModelRuntimeStatus.MODEL_ASSET_READY)
        self.assertIsNotNone(qsp.source_path)
        self.assertIsNotNone(qsp.asset_receipt_path)
        self.assertEqual(qsp.adapter_id, "passive.mitochondria_qsp")

    def test_ready_status_requires_runtime_and_smoke_receipt(self):
        with self.assertRaises(ValidationError):
            UnifiedModelRecord(
                model_id="fake",
                name="Fake",
                version="1",
                domain="test",
                role=ModelRole.CORE,
                capabilities=(),
                requires=(),
                produces=(),
                runtime_status=ModelRuntimeStatus.READY,
            )


if __name__ == "__main__":
    unittest.main()
