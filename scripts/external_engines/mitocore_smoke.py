"""Convert the official MitoCore v1.01 workbook and run a bounded FBA smoke test."""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import cobra
from cobra import Metabolite, Model, Reaction
from cobra.io import write_sbml_model
from openpyxl import load_workbook


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def compartment(metabolite_id: str) -> str:
    suffix = metabolite_id.rsplit("_", 1)[-1]
    return suffix if suffix in {"c", "m", "e", "i"} else "unknown"


def build_model(workbook_path: Path) -> Model:
    workbook = load_workbook(workbook_path, data_only=True, read_only=True)
    model = Model("MitoCore_v1.01")
    metabolite_sheet = workbook["Metabolites"]
    metabolites = []
    for row in metabolite_sheet.iter_rows(min_row=4, values_only=True):
        metabolite_id = row[1]
        if not metabolite_id:
            continue
        metabolite = Metabolite(
            str(metabolite_id),
            name=str(row[4] or metabolite_id),
            formula=str(row[5]) if row[5] else None,
            charge=int(row[6]) if row[6] is not None else None,
            compartment=compartment(str(metabolite_id)),
        )
        metabolites.append(metabolite)
    model.add_metabolites(metabolites)

    reaction_sheet = workbook["Reactions & Fluxes"]
    for row in reaction_sheet.iter_rows(min_row=5, values_only=True):
        reaction_id, equation = row[1], row[10]
        if not reaction_id or not equation:
            continue
        reaction = Reaction(
            str(reaction_id),
            name=str(row[2] or reaction_id),
            subsystem=str(row[6] or ""),
        )
        model.add_reactions([reaction])
        normalized_equation = str(equation).strip()
        # The official v1.01 companion workbook has one trailing '+' typo in
        # R_ORNt4mB_MitoCore. Removing it preserves the displayed stoichiometry.
        if reaction_id == "R_ORNt4mB_MitoCore":
            normalized_equation = normalized_equation.replace(" + -->", " -->")
        try:
            reaction.build_reaction_from_string(normalized_equation)
        except Exception as error:
            raise ValueError(
                f"cannot parse reaction {reaction_id}: {equation!r}"
            ) from error
        # COBRApy's string parser derives bounds from the arrow, so restore
        # the official workbook bounds only after parsing.
        reaction.bounds = (float(row[11]), float(row[12]))

    # MitoCore's spreadsheet treats extracellular species as an unbalanced
    # environment. COBRA models represent that convention with exchange
    # reactions; transport reaction bounds still define uptake limits.
    for metabolite in tuple(model.metabolites):
        if metabolite.compartment == "e":
            model.add_boundary(
                metabolite, type="exchange", lb=-1000.0, ub=1000.0
            )

    model.objective = model.reactions.get_by_id("R_OF_ATP_MitoCore")
    return model


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workbook", type=Path, required=True)
    parser.add_argument("--sbml", type=Path, required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    args = parser.parse_args()

    model = build_model(args.workbook)
    solution = model.optimize()
    if solution.status != "optimal" or solution.objective_value <= 0:
        raise RuntimeError(
            f"MitoCore smoke failed: status={solution.status}, objective={solution.objective_value}"
        )

    args.sbml.parent.mkdir(parents=True, exist_ok=True)
    write_sbml_model(model, args.sbml)
    payload = {
        "schema_version": "external-model-asset-receipt-v1",
        "component_id": "mitocore",
        "engine": {"name": "COBRApy", "version": cobra.__version__},
        "model": {
            "name": "MitoCore",
            "version": "1.01",
            "source_workbook": str(args.workbook.resolve()),
            "source_sha256": sha256(args.workbook),
            "converted_sbml": str(args.sbml.resolve()),
            "converted_sbml_sha256": sha256(args.sbml),
            "metabolites": len(model.metabolites),
            "reactions": len(model.reactions),
            "declared_source_corrections": [
                {
                    "reaction_id": "R_ORNt4mB_MitoCore",
                    "change": "removed orphan trailing plus before forward arrow",
                }
            ],
            "declared_conversion_conventions": [
                "extracellular metabolites receive reversible exchange reactions"
            ],
        },
        "smoke": {
            "kind": "constraint-based ATP-objective solve",
            "objective_reaction": "R_OF_ATP_MitoCore",
            "status": solution.status,
            "objective_value": float(solution.objective_value),
        },
        "scientific_boundary": (
            "Workbook conversion and an optimal FBA solve establish technical executability only; "
            "they do not validate physiology or personal predictive accuracy."
        ),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    args.receipt.parent.mkdir(parents=True, exist_ok=True)
    args.receipt.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
