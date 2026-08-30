"""Tests for the passive MitoCore adapter."""
from __future__ import annotations

import hashlib
import tempfile
import unittest
from pathlib import Path

from cobra import Metabolite, Model, Reaction

from frontier_research_harness.external_models.human_gem_adapter import (
    MetabolicCondition, MetabolicObjective, ObjectiveTerm,
    OptimizationDirection, ReactionConstraint,
)
from frontier_research_harness.external_models.mitocore_adapter import (
    MitoCoreExperimentRequest, MitoCorePassiveAdapter,
)


EXPERIMENT_ID = "00000000-0000-0000-0000-000000000701"
HYPOTHESIS_ID = "00000000-0000-0000-0000-000000000702"


def toy_model() -> Model:
    model = Model("toy-mitocore")
    uptake = Reaction("UPTAKE")
    uptake.bounds = (0, 10)
    atp = Reaction("ATP_OBJECTIVE")
    atp.bounds = (0, 1000)
    substrate = Metabolite("mitochondrial_substrate")
    uptake.add_metabolites({substrate: 1})
    atp.add_metabolites({substrate: -1})
    model.add_reactions([uptake, atp])
    return model


def constraint(upper: float) -> ReactionConstraint:
    return ReactionConstraint(
        reaction_id="UPTAKE", lower_bound=0, upper_bound=upper,
        unit="model flux unit", provenance="SCIENTIFIC_MODEL_ASSUMPTION",
        source_ref="experiment:H-702", rationale="Predeclared uptake contrast",
    )


class MitoCorePassiveAdapterTests(unittest.TestCase):
    def test_runs_distinct_conditions_and_keeps_reference_model_limits(self):
        with tempfile.TemporaryDirectory() as directory:
            model_path = Path(directory) / "mitocore.xml"
            model_path.write_bytes(b"pinned-mitocore-test")
            model_hash = hashlib.sha256(model_path.read_bytes()).hexdigest()
            request = MitoCoreExperimentRequest(
                experiment_id=EXPERIMENT_ID,
                hypothesis_ids=(HYPOTHESIS_ID,),
                model_asset_sha256=model_hash,
                baseline=MetabolicCondition(
                    condition_id="baseline", label="baseline",
                    constraints=(constraint(5),),
                ),
                candidates=(MetabolicCondition(
                    condition_id="candidate", label="candidate",
                    constraints=(constraint(8),),
                ),),
                objective=MetabolicObjective(
                    direction=OptimizationDirection.MAXIMIZE,
                    terms=(ObjectiveTerm(
                        reaction_id="ATP_OBJECTIVE", coefficient=1,
                        provenance="SCIENTIFIC_MODEL_ASSUMPTION",
                        source_ref="experiment:H-702",
                        rationale="Predeclared ATP objective",
                    ),),
                ),
                requested_flux_reaction_ids=("UPTAKE", "ATP_OBJECTIVE"),
                assumptions=("Toy model tests adapter mechanics only",),
                uncertainty_requirements=("No physiological inference",),
            )
            result = MitoCorePassiveAdapter(
                model_path, model_version="test",
                model_loader=lambda _: toy_model(),
            ).run(request)
            self.assertEqual(result.simulator_model, "MitoCore")
            self.assertEqual(result.baseline.objective_value, 5)
            self.assertEqual(result.candidates[0].objective_value, 8)
            self.assertEqual(
                [item.value for item in result.candidates[0].baseline_flux_deltas],
                [3, 3],
            )
            self.assertTrue(any("compact curated" in item for item in result.limitations))

if __name__ == "__main__":
    unittest.main()
