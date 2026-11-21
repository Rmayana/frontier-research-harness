"""Run OpenSim inverse dynamics on a model and measured coordinate series."""

import argparse
import json
import math
import sys
import tempfile
from pathlib import Path


def inverse_dynamics(model_path, coordinates_path, external_loads_path=None):
    """Use OpenSim file units. Return labelled generalized forces in SI units."""
    import opensim as osim

    model_file = Path(model_path).resolve(strict=True)
    coordinates_file = Path(coordinates_path).resolve(strict=True)
    tool = osim.InverseDynamicsTool()
    model = osim.Model(str(model_file))
    tool.setModel(model)
    tool.setCoordinatesFileName(str(coordinates_file))
    motion = osim.Storage(str(coordinates_file))
    if motion.getSize() < 3 or motion.getLastTime() <= motion.getFirstTime():
        raise ValueError("at least three frames over a positive duration are required")
    labels = motion.getColumnLabels()
    names = {labels.get(i) for i in range(1, labels.getSize())}
    state = model.initSystem()
    coordinates = model.getCoordinateSet()
    for i in range(coordinates.getSize()):
        coordinate = coordinates.get(i)
        if not coordinate.isConstrained(state) and coordinate.getName() not in names:
            raise ValueError(f"missing coordinate column: {coordinate.getName()}")
    previous_time = -math.inf
    for i in range(motion.getSize()):
        time = motion.getStateVector(i).getTime()
        if not math.isfinite(time) or time <= previous_time:
            raise ValueError("motion times must be finite and strictly increasing")
        previous_time = time
    tool.setStartTime(motion.getFirstTime())
    tool.setEndTime(motion.getLastTime())
    if external_loads_path is not None:
        tool.setExternalLoadsFileName(str(Path(external_loads_path).resolve(strict=True)))
    with tempfile.TemporaryDirectory() as directory:
        tool.setResultsDir(directory)
        tool.setOutputGenForceFileName("forces.sto")
        if not tool.run():
            raise RuntimeError("OpenSim inverse dynamics did not complete")
        result = osim.TimeSeriesTable(str(Path(directory) / "forces.sto"))
        columns = {name: list(result.getDependentColumn(name).to_numpy().flatten().tolist())
                   for name in result.getColumnLabels()}
        return {"time_s": list(result.getIndependentColumn()), "generalized_forces": columns,
                "rotational_unit": "N m", "translational_unit": "N",
                "external_loads_file_supplied": external_loads_path is not None}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("model_path")
    parser.add_argument("coordinates_path")
    parser.add_argument("--output", required=True, type=Path, help="new JSON output file")
    parser.add_argument("--external-loads", dest="external_loads_path")
    args = parser.parse_args()
    try:
        result = inverse_dynamics(args.model_path, args.coordinates_path, args.external_loads_path)
        payload = json.dumps(result, allow_nan=False)
        with args.output.open("x", encoding="utf-8") as output:
            output.write(payload)
    except (OSError, ValueError, RuntimeError, ImportError) as error:
        parser.exit(2, f"Inverse dynamics failed: {error}\n")


if __name__ == "__main__":
    main()
