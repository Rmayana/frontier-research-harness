"""Tests for the passive Human-GEM adapter."""
from __future__ import annotations

import hashlib
import tempfile
import unittest
from pathlib import Path

from cobra import Model, Reaction
from pydantic import ValidationError

from frontier_research_harness.external_models.human_gem_adapter import (
    HumanGemExperimentRequest,
    HumanGemPassiveAdapter,
    MetabolicCondition,
    MetabolicObjective,
    ObjectiveTerm,
    OptimizationDirection,
    ReactionConstraint,
)


EXPERIMENT_ID = "00000000-0000-0000-0000-000000000101"
HYPOTHESIS_ID = "00000000-0000-0000-0000-000000000102"


def constraint(reaction_id: str, lower: float, upper: float) -> ReactionConstraint:
    return ReactionConstraint(
        reaction_id=reaction_id,
        lower_bound=lower,
        upper_bound=upper,
        unit="model flux unit",
        provenance="SCIENTIFIC_MODEL_ASSUMPTION",
        source_ref="experiment-spec:H-102",
        rationale="Predeclared test constraint",
    )


def toy_model() -> Model:
    model = Model("toy-human-gem")
    uptake = Reaction("UPTAKE")
    uptake.bounds = (0, 10)
    objective = Reaction("OBJECTIVE")
    objective.bounds = (0, 1000)
    # A single pseudo steady-state link is enough to test exact bound handling.
    from cobra import Metabolite
    substrate = Metabolite("substrate")
    uptake.add_metabolites({substrate: 1})
    objective.add_metabolites({substrate: -1})
    model.add_reactions([uptake, objective])
    return model


class HumanGemPassiveAdapterTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.model_path = Path(self.temp.name) / "Human-GEM.xml"
        self.model_path.write_bytes(b"pinned-test-asset")
        self.model_hash = hashlib.sha256(self.model_path.read_bytes()).hexdigest()

    def tearDown(self):
        self.temp.cleanup()

    def request(self, **updates) -> HumanGemExperimentRequest:
        values = dict(
            experiment_id=EXPERIMENT_ID,
            hypothesis_ids=(HYPOTHESIS_ID,),
            model_asset_sha256=self.model_hash,
            baseline=MetabolicCondition(
                condition_id="baseline",
                label="Declared comparator",
                constraints=(constraint("UPTAKE", 0, 5),),
            ),
            candidates=(MetabolicCondition(
                condition_id="candidate",
                label="Declared hypothesis condition",
                constraints=(constraint("UPTAKE", 0, 8),),
            ),),
            objective=MetabolicObjective(
                direction=OptimizationDirection.MAXIMIZE,
                terms=(ObjectiveTerm(
                    reaction_id="OBJECTIVE",
                    coefficient=1,
                    provenance="SCIENTIFIC_MODEL_ASSUMPTION",
                    source_ref="experiment-spec:H-102",
                    rationale="Predeclared objective",
                ),),
            ),
            requested_flux_reaction_ids=("UPTAKE", "OBJECTIVE"),
            assumptions=("Toy network represents only adapter mechanics",),
            uncertainty_requirements=("No biological uncertainty quantified",),
        )
        values.update(updates)
        return HumanGemExperimentRequest(**values)

    def adapter(self) -> HumanGemPassiveAdapter:
        return HumanGemPassiveAdapter(
            self.model_path,
            model_version="test",
            model_loader=lambda _: toy_model(),
        )

    def test_executes_exact_baseline_and_candidate_and_returns_deltas(self):
        result = self.adapter().run(self.request())
        self.assertEqual(result.baseline.objective_value, 5.0)
        self.assertEqual(result.candidates[0].objective_value, 8.0)
        self.assertEqual(
            [item.value for item in result.candidates[0].baseline_flux_deltas],
            [3.0, 3.0],
        )
        self.assertIn("does not judge hypothesis agreement", result.limitations[0])

    def test_missing_reaction_fails_closed_before_optimization(self):
        request = self.request(requested_flux_reaction_ids=("MISSING",))
        with self.assertRaisesRegex(ValueError, "do not exist: MISSING"):
            self.adapter().run(request)

    def test_model_asset_hash_mismatch_fails_closed(self):
        request = self.request(model_asset_sha256="0" * 64)
        with self.assertRaisesRegex(ValueError, "hash does not match"):
            self.adapter().run(request)

    def test_constraint_requires_traceable_source(self):
        with self.assertRaises(ValidationError):
            ReactionConstraint(
                reaction_id="UPTAKE",
                lower_bound=0,
                upper_bound=5,
                unit="model flux unit",
                provenance="ASSUMPTION",
                source_ref="",
                rationale="Declared",
            )


if __name__ == "__main__":
    unittest.main()
