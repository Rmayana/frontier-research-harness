"""Evaluate explicitly supplied OpenSim states; does not integrate a motion.

Uses OpenSim's native joint reaction API (opensim-core, Apache-2.0).
All omitted states/controls must be explicitly allowed as model defaults.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import shutil
import tempfile


def finite(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError("state times, values and controls must be finite numbers")
    return float(value)


def validate_series(payload):
    if not isinstance(payload, dict) or set(payload) - {"snapshots", "allow_model_defaults"}:
        raise ValueError("series accepts snapshots and allow_model_defaults only")
    defaults = payload.get("allow_model_defaults", False)
    if type(defaults) is not bool:
        raise ValueError("allow_model_defaults must be boolean")
    rows = payload.get("snapshots")
    if not isinstance(rows, list) or not 2 <= len(rows) <= 10000:
        raise ValueError("provide between 2 and 10000 snapshots")
    previous = -math.inf
    for row in rows:
        if not isinstance(row, dict) or set(row) - {"time_seconds", "state_variable_values", "controls"}:
            raise ValueError("unknown snapshot field")
        time = finite(row.get("time_seconds"))
        if time <= previous:
            raise ValueError("snapshot times must be strictly increasing")
        previous = time
        states = row.get("state_variable_values")
        if not isinstance(states, dict) or any(not isinstance(k, str) or not k for k in states):
            raise ValueError("state_variable_values must be a named state mapping")
        for value in states.values():
            finite(value)
        controls = row.get("controls")
        if controls is not None:
            if not isinstance(controls, list):
                raise ValueError("controls must be an ordered numeric list")
            for value in controls:
                finite(value)
    return rows, defaults


def main():
    import opensim
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--states", type=Path, required=True)
    parser.add_argument("--joint", required=True)
    parser.add_argument("--side", choices=("child", "parent"), required=True)
    args = parser.parse_args()
    rows, allow_defaults = validate_series(json.loads(args.states.read_text(encoding="utf-8-sig")))
    opensim.Logger.setLevelString("error")
    with tempfile.TemporaryDirectory(prefix="opensim-series-") as folder:
        staged = Path(folder) / "model.osim"
        shutil.copy2(args.model.resolve(), staged)
        model = opensim.Model(str(staged))
        initial = model.initSystem()
        names = model.getStateVariableNames()
        available = {str(names.get(i)) for i in range(names.getSize())}
        defaults = {name: float(model.getStateVariableValue(initial, name)) for name in sorted(available)}
        default_controls = model.getDefaultControls()
        control_defaults = [float(default_controls.get(i)) for i in range(model.getNumControls())]
        joint = model.getJointSet().get(args.joint)
        output = []
        for row in rows:
            requested = row["state_variable_values"]
            if set(requested) - available:
                raise ValueError("unknown OpenSim state variables: " + str(sorted(set(requested) - available)))
            if not allow_defaults and available - requested.keys():
                raise ValueError("missing state variables; supply every state or explicitly allow_model_defaults")
            controls = row.get("controls", control_defaults if allow_defaults else None)
            if controls is None and not model.getNumControls():
                controls = []
            if controls is None or len(controls) != model.getNumControls():
                raise ValueError("supply all model controls in native index order or explicitly allow_model_defaults")
            # Reset to the same initial state at each sample: never carry a
            # previous sample's omitted fields into the next one.
            state = opensim.State(initial)
            state.setTime(row["time_seconds"])
            applied = {**defaults, **requested}
            for name, value in applied.items():
                model.setStateVariableValue(state, name, value)
            model.realizeVelocity(state)
            vector = opensim.Vector(len(controls), 0.0)
            for index, value in enumerate(controls):
                vector.set(index, value)
            model.setControls(state, vector)
            model.realizeAcceleration(state)
            reaction = (joint.calcReactionOnChildExpressedInGround(state) if args.side == "child"
                        else joint.calcReactionOnParentExpressedInGround(state))
            output.append({"time_seconds": float(state.getTime()),
                           "force_n": [finite(float(reaction.get(1).get(i))) for i in range(3)],
                           "moment_nm": [finite(float(reaction.get(0).get(i))) for i in range(3)],
                           "applied_state_variable_values": applied, "controls": controls})
        result = {"observable_kind": "JOINT_REACTION_SERIES", "opensim_version": opensim.GetVersionAndDate(),
                  "joint": args.joint, "side": args.side, "expressed_in_frame": "ground",
                  "allow_model_defaults": allow_defaults, "samples": output,
                  "limitations": ["Supplied states are evaluated independently; kinematic/dynamic consistency is not established.",
                      "This is not forward integration, muscle-force estimation from kinematics, or a growth/injury forecast."]}
        print(json.dumps(result, sort_keys=True, allow_nan=False))
    opensim.Logger.removeFileSink()


if __name__ == "__main__":
    main()
