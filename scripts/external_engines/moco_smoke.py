"""Small OpenSim Moco optimal-control smoke check."""

from __future__ import annotations

import gc
import json
import os
from pathlib import Path
import tempfile

import opensim


def main() -> None:
    opensim_runtime = Path(opensim.__file__).resolve().parent
    # CasADi discovers solver plugins after the OpenSim module is imported.
    # The wheel bundles IPOPT beside the Python module but does not expose that
    # directory through CASADIPATH in this environment.
    os.environ["CASADIPATH"] = str(opensim_runtime)
    with tempfile.TemporaryDirectory(prefix="moco-smoke-") as temporary:
        previous = Path.cwd()
        os.chdir(temporary)
        try:
            model = opensim.Model()
            model.setName("sliding_mass")
            model.set_gravity(opensim.Vec3(0, 0, 0))
            body = opensim.Body(
                "body", 2.0, opensim.Vec3(0), opensim.Inertia(0)
            )
            model.addComponent(body)
            joint = opensim.SliderJoint("slider", model.getGround(), body)
            coordinate = joint.updCoordinate()
            coordinate.setName("position")
            model.addComponent(joint)
            actuator = opensim.CoordinateActuator()
            actuator.setCoordinate(coordinate)
            actuator.setName("actuator")
            actuator.setOptimalForce(1)
            model.addComponent(actuator)
            model.finalizeConnections()

            study = opensim.MocoStudy()
            study.setName("sliding_mass_smoke")
            problem = study.updProblem()
            problem.setModel(model)
            problem.setTimeBounds(
                opensim.MocoInitialBounds(0),
                opensim.MocoFinalBounds(0.1, 5),
            )
            problem.setStateInfo(
                "/slider/position/value", [-5, 5], [0], [1]
            )
            problem.setStateInfo(
                "/slider/position/speed", [-50, 50], [0], [0]
            )
            problem.setControlInfo("/actuator", [-50, 50])
            problem.addGoal(opensim.MocoFinalTimeGoal())
            solver = study.initCasADiSolver()
            solver.set_num_mesh_intervals(10)
            solver.set_optim_convergence_tolerance(1e-3)
            solver.set_optim_constraint_tolerance(1e-3)

            solution = study.solve()
            result = {
                "version": opensim.GetVersionAndDate(),
                "study": "sliding_mass_smoke",
                "success": bool(solution.success()),
                "status": solution.getStatus(),
                "final_time_seconds": float(solution.getFinalTime()),
                "objective": float(solution.getObjective()),
                "mesh_intervals": 10,
                "casadi_plugin_path": str(opensim_runtime),
            }
            if not result["success"]:
                raise RuntimeError(f"Moco solve failed: {result['status']}")
        finally:
            for name in (
                "solution", "solver", "problem", "study", "actuator",
                "coordinate", "joint", "body", "model",
            ):
                if name in locals():
                    del locals()[name]
            opensim.Logger.removeFileSink()
            gc.collect()
            os.chdir(previous)

    print(json.dumps(result, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
