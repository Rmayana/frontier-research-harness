"""Load the pinned Human-GEM SBML asset and run its declared FBA objective.

This verifies parser, model integrity, and solver execution only. A feasible
generic-model optimum is not a personalized metabolic prediction.
"""

from __future__ import annotations

import json
from pathlib import Path

import cobra
from cobra.io import read_sbml_model


MODEL_PATH = Path("vendor/Human-GEM/model/Human-GEM.xml")


def main() -> None:
    if not MODEL_PATH.is_file():
        raise FileNotFoundError(MODEL_PATH)
    model = read_sbml_model(str(MODEL_PATH))
    solution = model.optimize()
    result = {
        "cobra_version": cobra.__version__,
        "model_id": model.id,
        "model_name": model.name,
        "reactions": len(model.reactions),
        "metabolites": len(model.metabolites),
        "genes": len(model.genes),
        "compartments": len(model.compartments),
        "solver": str(model.solver.interface.__name__),
        "objective_expression": str(model.objective.expression),
        "status": solution.status,
        "objective_value": float(solution.objective_value),
    }
    if solution.status != "optimal":
        raise RuntimeError(f"Human-GEM FBA was not optimal: {solution.status}")
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
