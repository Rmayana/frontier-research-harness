"""Extract one OpenSim joint reaction at a default or caller-specified state."""
from __future__ import annotations

import argparse
import json
import shutil
import tempfile
from pathlib import Path

import opensim


def vec3(value) -> list[float]:
    return [float(value.get(index)) for index in range(3)]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--joint", required=True)
    parser.add_argument("--side", choices=("child", "parent"), required=True)
    parser.add_argument("--state-snapshot", type=Path)
    args = parser.parse_args()
    opensim.Logger.setLevelString("error")
    # OpenSim's native Windows loader fails on this workspace's Korean path.
    # Stage immutable inputs in an ASCII temporary directory, matching the
    # verified smoke-test boundary.
    with tempfile.TemporaryDirectory(prefix="opensim-joint-reaction-") as temporary:
        staging = Path(temporary)
        staged_model = staging / "model.osim"
        shutil.copy2(args.model.resolve(), staged_model)
        snapshot = None
        if args.state_snapshot is not None:
            staged_snapshot = staging / "state.json"
            shutil.copy2(args.state_snapshot.resolve(), staged_snapshot)
            snapshot = json.loads(staged_snapshot.read_text(encoding="utf-8"))
        model = opensim.Model(str(staged_model))
        joint = model.getJointSet().get(args.joint)
        state = model.initSystem()
        applied = {}
        if snapshot is not None:
            state.setTime(float(snapshot["time_seconds"]))
            names = model.getStateVariableNames()
            available = {str(names.get(index)) for index in range(names.getSize())}
            requested = snapshot["state_variable_values"]
            unknown = sorted(set(requested) - available)
            if unknown:
                raise ValueError(f"unknown OpenSim state variables: {unknown}")
            for name, value in requested.items():
                model.setStateVariableValue(state, name, float(value))
                applied[name] = float(value)
        model.realizeAcceleration(state)
        reaction = (
            joint.calcReactionOnChildExpressedInGround(state)
            if args.side == "child"
            else joint.calcReactionOnParentExpressedInGround(state)
        )
        body = joint.getChildFrame().findBaseFrame().getName() if args.side == "child" else joint.getParentFrame().findBaseFrame().getName()
        print(json.dumps({
            "opensim_version": opensim.GetVersionAndDate(),
            "joint": args.joint, "side": args.side, "applied_to_body": body,
            "expressed_in_frame": "ground", "time_seconds": float(state.getTime()),
            "moment_nm": vec3(reaction.get(0)), "force_n": vec3(reaction.get(1)),
            "state_kind": ("CALLER_SPECIFIED_STATE_SNAPSHOT" if snapshot is not None
                           else "MODEL_DEFAULT_STATIC_STATE"),
            "applied_state_variable_values": applied,
            "ascii_staging_used": True,
        }, sort_keys=True))
    opensim.Logger.removeFileSink()


if __name__ == "__main__":
    main()
