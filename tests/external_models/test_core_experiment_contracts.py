from __future__ import annotations

import unittest

from pydantic import ValidationError

from frontier_research_harness.external_models.core_experiment_contracts import (
    CalibrationBoundary,
    FebioStudy,
    OpenSimJointReactionStudy,
    PulseScenarioStudy,
)


class CoreExperimentContractTests(unittest.TestCase):
    def test_opensim_personal_study_requires_observed_state(self):
        with self.assertRaisesRegex(ValidationError, "state_snapshot_path"):
            OpenSimJointReactionStudy(
                model_path="models/personal.osim", joint="knee_r", side="child",
                calibration=CalibrationBoundary.PERSONAL_OBSERVATION,
            )

    def test_opensim_builds_hash_receipted_job(self):
        study = OpenSimJointReactionStudy(
            model_path="models/personal.osim", joint="knee_r", side="child",
            state_snapshot_path="observations/jump-state.json",
            calibration=CalibrationBoundary.PERSONAL_OBSERVATION,
        )
        job = study.to_job()
        self.assertEqual(job.component_id, "opensim")
        self.assertIn("observations/jump-state.json", job.input_artifacts)
        self.assertNotIn("component_id", study.model_dump())

    def test_pulse_and_febio_declare_outputs(self):
        pulse = PulseScenarioStudy(
            scenario_path="studies/pulse.json", expected_results_path="studies/pulseResults.csv",
            calibration=CalibrationBoundary.REFERENCE,
        ).to_job()
        febio = FebioStudy(
            model_path="studies/neck/model.feb", expected_log_path="studies/neck/model.log",
            expected_plot_path="studies/neck/model.xplt", calibration=CalibrationBoundary.REFERENCE,
        ).to_job()
        self.assertEqual(pulse.expected_output_artifacts, ("studies/pulseResults.csv",))
        self.assertEqual(pulse.working_directory, ".scratch/pulse-ascii/install/bin")
        self.assertEqual(febio.working_directory, "studies/neck")
        self.assertEqual(febio.arguments, ("model.feb",))

    def test_paths_cannot_escape_workspace(self):
        with self.assertRaisesRegex(ValidationError, "workspace-relative"):
            PulseScenarioStudy(
                scenario_path="../outside.json", expected_results_path="results.csv",
                calibration=CalibrationBoundary.REFERENCE,
            )


if __name__ == "__main__":
    unittest.main()
