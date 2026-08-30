"""Deterministic OpenSim runtime and model-load smoke check.

This proves that the Python runtime can load and initialize one upstream model.
It does not qualify subject scaling, movement prediction, Moco, or adaptation.
"""

from __future__ import annotations

import json
from pathlib import Path
import gc
import shutil
import tempfile

import opensim


MODEL_PATH = Path(
    "vendor/opensim-core/Applications/Scale/tests/resources/gait2354_simbody.osim"
)


def main() -> None:
    if not MODEL_PATH.is_file():
        raise FileNotFoundError(MODEL_PATH)

    # OpenSim 4.6's Windows native file loader cannot reliably open paths that
    # contain Korean characters. Stage the immutable input at an ASCII-only
    # temporary path; adapters must use the same explicit staging boundary.
    with tempfile.TemporaryDirectory(prefix="opensim-smoke-") as temporary:
        staged_model = Path(temporary) / MODEL_PATH.name
        shutil.copy2(MODEL_PATH, staged_model)
        model = opensim.Model(str(staged_model))
        state = model.initSystem()
        model.realizePosition(state)

        result = {
            "version": opensim.GetVersionAndDate(),
            "model_path": MODEL_PATH.as_posix(),
            "model_name": model.getName(),
            "coordinates": int(model.getCoordinateSet().getSize()),
            "bodies": int(model.getBodySet().getSize()),
            "joints": int(model.getJointSet().getSize()),
            "muscles": int(model.getMuscles().getSize()),
            "controls": int(model.getNumControls()),
            "system_initialized": bool(state.getNY() > 0),
            "ascii_staging_required": True,
        }
        # Release native references and the default opensim.log sink before
        # TemporaryDirectory attempts cleanup on Windows.
        del state
        del model
        opensim.Logger.removeFileSink()
        gc.collect()
    if not result["system_initialized"]:
        raise RuntimeError("OpenSim model did not initialize a non-empty state")

    print(json.dumps(result, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
