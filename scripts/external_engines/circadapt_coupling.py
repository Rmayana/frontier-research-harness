"""Consume explicit Pulse hemodynamic values in CircAdapt VanOsta2023."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
from circadapt.model.vanosta2023 import VanOsta2023


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("expected one coupling request JSON path")
    request = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    model = VanOsta2023()
    model.set("Model.t_cycle", float(request["cycle_seconds"]))
    model.set("Model.PFC.q0", float(request["target_flow_m3_s"]))
    model.run(stable=True)
    if not model.is_stable():
        raise RuntimeError("CircAdapt did not reach a stable beat")
    time = np.asarray(model["Solver"]["t"])
    pressure = np.asarray(model["Cavity"]["p"][:, "cLv"])
    volume = np.asarray(model["Cavity"]["V"][:, "cLv"])
    flow = np.asarray(model["Valve"]["q"][:, "LvSyArt"])
    cycle = float(time[-1] - time[0])
    print(json.dumps({
        "version": "2602", "stable": True,
        "applied": {
            "Model.t_cycle": float(request["cycle_seconds"]),
            "Model.PFC.q0": float(request["target_flow_m3_s"]),
        },
        "heart_rate_bpm": 60.0 / cycle,
        "cardiac_output_l_min": float(np.trapezoid(flow, time) / cycle * 60000.0),
        "stroke_volume_ml": float((volume.max() - volume.min()) * 1e6),
        "lv_peak_pressure_mmhg": float(pressure.max() / 133.322),
        "samples": int(len(time)),
    }, sort_keys=True))


if __name__ == "__main__":
    main()
