"""Run live reference-only acceptance checks for typed core-model paths."""
from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path

from frontier_research_harness.adapters.frontier_science_workspace import FrontierScienceWorkspace


REFERENCE_STUDIES = {
    "opensim": {
        "study_type": "joint_reaction",
        "model_path": "vendor/opensim-core/Applications/Scale/tests/resources/gait2354_simbody.osim",
        "joint": "knee_r", "side": "child", "calibration": "REFERENCE",
    },
    "pulse": {
        "study_type": "scenario",
        "scenario_path": "scripts/external_engines/pulse_exercise_smoke.json",
        "expected_results_path": "scripts/external_engines/pulse_exercise_smokeResults.csv",
        "calibration": "REFERENCE", "exercise_end_seconds": 40.0,
        "recovery_interval_seconds": 20.0,
    },
    "febio": {
        "study_type": "finite_element",
        "model_path": ".scratch/FEBioUncertainSCI/Model1.feb",
        "expected_log_path": ".scratch/FEBioUncertainSCI/Model1.log",
        "expected_plot_path": ".scratch/FEBioUncertainSCI/Model1.xplt",
        "calibration": "REFERENCE",
    },
}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("models", nargs="*", choices=tuple(REFERENCE_STUDIES))
    args = parser.parse_args()
    models = args.models or tuple(REFERENCE_STUDIES)
    summary = []
    with tempfile.TemporaryDirectory(prefix="frontier-model-acceptance-") as root:
        with FrontierScienceWorkspace(Path(root) / "acceptance.sqlite3") as workspace:
            for name in models:
                result = workspace.run_model(
                    name, REFERENCE_STUDIES[name],
                    question=f"Does the typed {name} path execute and preserve normalized reference observables?",
                    provenance=[{"kind": "acceptance", "scope": "reference_only"}],
                )
                normalized = result["raw_output"]["normalized_observables"]
                summary.append({
                    "model": name, "experiment_saved": bool(result["experiment_id"]),
                    "observable_kind": normalized["observable_kind"],
                    "calibration": result["raw_output"]["calibration"],
                })
    print(json.dumps({"status": "OK", "models": summary}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
