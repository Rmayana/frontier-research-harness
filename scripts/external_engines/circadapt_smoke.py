import json

import numpy as np

from circadapt.model.vanosta2023 import VanOsta2023


model = VanOsta2023()
model.run(stable=True)

time = np.asarray(model["Solver"]["t"])
lv_pressure = np.asarray(model["Cavity"]["p"][:, "cLv"])
lv_volume = np.asarray(model["Cavity"]["V"][:, "cLv"])
aortic_flow = np.asarray(model["Valve"]["q"][:, "LvSyArt"])
cycle_seconds = float(time[-1] - time[0])

result = {
    "version": "2602",
    "stable": bool(model.is_stable()),
    "samples": int(len(time)),
    "cycle_seconds": cycle_seconds,
    "heart_rate_bpm": float(60.0 / cycle_seconds),
    "lv_pressure_mmhg": [
        float(lv_pressure.min() / 133.322),
        float(lv_pressure.max() / 133.322),
    ],
    "lv_volume_ml": [
        float(lv_volume.min() * 1e6),
        float(lv_volume.max() * 1e6),
    ],
    "stroke_volume_ml": float((lv_volume.max() - lv_volume.min()) * 1e6),
    "ejection_fraction": float(
        (lv_volume.max() - lv_volume.min()) / lv_volume.max()
    ),
    "cardiac_output_l_min": float(
        np.trapezoid(aortic_flow, time) / cycle_seconds * 60000.0
    ),
}

if not result["stable"]:
    raise RuntimeError("CircAdapt reference model did not reach a stable beat.")

print(json.dumps(result, sort_keys=True))
