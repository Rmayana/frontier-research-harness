from __future__ import annotations

import unittest

from frontier_research_harness.target_calculator import (
    CalculationStatus,
    TARGET_SPECS,
    TargetCalculationRequest,
    calculate_target,
)


class TargetCalculatorTests(unittest.TestCase):
    def test_all_fixed_physical_targets_have_a_formula_contract(self):
        self.assertEqual(len(TARGET_SPECS), 27)

    def test_imtp_normalization_is_exact_and_unit_checked(self):
        result = calculate_target(TargetCalculationRequest(
            target_id="imtp_peak_force",
            inputs={"peak_force_n": 7200.0, "body_mass_kg": 120.0},
            units={"peak_force_n": "N", "body_mass_kg": "kg"},
        ))
        self.assertEqual(result.status, CalculationStatus.CALCULATED)
        self.assertEqual(result.value, 60.0)
        self.assertTrue(result.meets_target_floor)
        with self.assertRaisesRegex(ValueError, "unit must be"):
            calculate_target(TargetCalculationRequest(
                target_id="imtp_peak_force",
                inputs={"peak_force_n": 7200.0, "body_mass_kg": 120.0},
                units={"peak_force_n": "kgf", "body_mass_kg": "kg"},
            ))

    def test_cmj_flight_time_formula_and_repeated_decrement(self):
        jump = calculate_target(TargetCalculationRequest(
            target_id="cmj_height",
            inputs={"flight_time_s": 0.5},
            units={"flight_time_s": "s"},
        ))
        self.assertAlmostEqual(jump.value or 0, 30.64578125)
        repeated = calculate_target(TargetCalculationRequest(
            target_id="repeated_explosive_output_decrement",
            inputs={"outputs_w": [1000.0, 980.0, 960.0]},
            units={"outputs_w": "W"},
        ))
        self.assertAlmostEqual(repeated.value or 0, 4.0)
        self.assertTrue(repeated.meets_target_floor)

    def test_missing_inputs_are_described_without_fabricating_a_result(self):
        result = calculate_target(TargetCalculationRequest(target_id="vo2max"))
        self.assertEqual(result.status, CalculationStatus.INPUT_REQUIRED)
        self.assertIsNone(result.value)
        self.assertEqual(
            result.missing_inputs,
            ("oxygen_consumption_ml_min", "body_mass_kg"),
        )

    def test_asymmetry_and_adherence_boundaries(self):
        asymmetry = calculate_target(TargetCalculationRequest(
            target_id="dynamic_balance_asymmetry",
            inputs={"left_value": 100.0, "right_value": 97.0},
            units={"left_value": "cm", "right_value": "cm"},
        ))
        self.assertAlmostEqual(asymmetry.value or 0, 3.0)
        self.assertTrue(asymmetry.meets_target_floor)
        adherence = calculate_target(TargetCalculationRequest(
            target_id="annual_training_adherence",
            inputs={"completed_sessions": 95.0, "planned_sessions": 100.0},
            units={"completed_sessions": "count", "planned_sessions": "count"},
        ))
        self.assertEqual(adherence.value, 95.0)
        self.assertTrue(adherence.meets_target_floor)


if __name__ == "__main__":
    unittest.main()
