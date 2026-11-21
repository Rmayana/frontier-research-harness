"""Local hypothesis-comparison tools. Run with Python 3.10+, JSON on stdin."""

import argparse
import json
import math
import sys
from statistics import NormalDist


def number(value, name):
    if type(value) not in (float, int) or not math.isfinite(value):
        raise ValueError(f"{name} must be a finite number")
    return float(value)


def load_series(values, name):
    if not isinstance(values, list) or not values:
        raise ValueError(f"{name} must be a nonempty daily series")
    result = [number(value, name) for value in values]
    if min(result) < 0:
        raise ValueError(f"{name} cannot contain negative load")
    return result


def compare_schedules(schedule_a, schedule_b, fitness_days, fatigue_days,
                      fitness_gain, fatigue_gain):
    """Zero initial state; daily updates, score sampled just after each load."""
    a = load_series(schedule_a, "schedule_a")
    b = load_series(schedule_b, "schedule_b")
    if len(a) != len(b):
        raise ValueError("schedules must cover the same days")
    fitness_days = number(fitness_days, "fitness_days")
    fatigue_days = number(fatigue_days, "fatigue_days")
    fitness_gain = number(fitness_gain, "fitness_gain")
    fatigue_gain = number(fatigue_gain, "fatigue_gain")
    if min(fitness_days, fatigue_days) <= 0 or min(fitness_gain, fatigue_gain) < 0:
        raise ValueError("time constants must be positive and gains nonnegative")
    fitness_decay = math.exp(-1 / fitness_days)
    fatigue_decay = math.exp(-1 / fatigue_days)

    def trace(loads):
        fitness = fatigue = 0.0
        scores = []
        for load in loads:
            fitness = fitness * fitness_decay + fitness_gain * load
            fatigue = fatigue * fatigue_decay + fatigue_gain * load
            scores.append(fitness - fatigue)
        return scores

    scores_a, scores_b = trace(a), trace(b)
    return {"score_unit": "model units relative to baseline",
            "total_load_a": sum(a), "total_load_b": sum(b),
            "scores_a": scores_a, "scores_b": scores_b,
            "end_difference_b_minus_a": scores_b[-1] - scores_a[-1]}


def paired_design_power(effect, sd_difference, pairs, alpha=0.05):
    """Two-sided normal test with known SD of independent paired differences."""
    effect = number(effect, "effect")
    sd = number(sd_difference, "sd_difference")
    alpha = number(alpha, "alpha")
    if type(pairs) is not int or pairs < 1 or sd <= 0 or not 0 < alpha < 1:
        raise ValueError("need positive pairs and SD, and alpha strictly between 0 and 1")
    normal = NormalDist()
    critical = -normal.inv_cdf(alpha / 2)
    standard_error = sd / math.sqrt(pairs)
    shift = abs(effect) / standard_error
    power = normal.cdf(-critical - shift) + normal.cdf(shift - critical)
    return {"pairs": pairs, "standard_error": standard_error,
            "two_sided_power": power, "alpha": alpha,
            "confidence_interval_half_width": critical * standard_error}


TOOLS = {"compare_schedules": compare_schedules, "paired_design_power": paired_design_power}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("tool", choices=TOOLS)
    args = parser.parse_args()
    try:
        inputs = json.load(sys.stdin)
        if not isinstance(inputs, dict):
            raise ValueError("input must be a JSON object")
        result = TOOLS[args.tool](**inputs)
        print(json.dumps({"tool": args.tool, "inputs": inputs, "result": result},
                         allow_nan=False))
    except (ValueError, TypeError, ArithmeticError) as exc:
        parser.exit(2, f"Invalid simulation input or numerical range: {exc}\n")


if __name__ == "__main__":
    main()
