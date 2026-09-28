"""Derive versioned adult-human priors from official NHANES public files.

Raw XPT files are intentionally kept out of git.  Download the six URLs in
``SOURCES`` into ``.scratch/nhanes`` and run this script with a Python runtime
that provides pandas and NumPy.  The checked-in JSON contains the exact source
hashes, filters, weights, sample sizes, weighted empirical quantiles, and the
complete-case dependency matrix used by the virtual-population sampler.
"""
from __future__ import annotations

import hashlib
import json
import math
import sys
from datetime import datetime, timezone
from itertools import combinations
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from frontier_research_harness.reference_state import TimeResolution
from frontier_research_harness.population_reference import (
    LinearPlausibilityConstraint,
    PlausibilityTerm,
    PopulationCorrelation,
    PopulationEvidenceSource,
    PopulationParameterPrior,
    PopulationPrior,
    PriorDistribution,
)


RAW = ROOT / ".scratch" / "nhanes"
OUTPUT = (
    ROOT
    / "src"
    / "frontier_research_harness"
    / "reference_data"
    / "nhanes_adult_reference_v1.json"
)
QUANTILE_PROBABILITIES = (
    0.0, 0.005, 0.01, 0.025, 0.05, 0.10, 0.20, 0.30, 0.40, 0.50,
    0.60, 0.70, 0.80, 0.90, 0.95, 0.975, 0.99, 0.995, 1.0,
)
SOURCES = {
    "nhanes-2017-2018-demographics": (
        "DEMO_J.XPT",
        "https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/2017/DataFiles/DEMO_J.XPT",
        "NHANES 2017-2018 examined participants; demographic filter and MEC weights.",
    ),
    "nhanes-2017-2018-body-measures": (
        "BMX_J.XPT",
        "https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/2017/DataFiles/BMX_J.XPT",
        "NHANES 2017-2018 examined participants; measured anthropometry.",
    ),
    "nhanes-2017-2018-dxa": (
        "DXX_J.XPT",
        "https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/2017/DataFiles/DXX_J.XPT",
        "NHANES 2017-2018 eligible participants with valid whole-body DXA outputs.",
    ),
    "nhanes-2013-2014-demographics": (
        "DEMO_H.XPT",
        "https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/2013/DataFiles/DEMO_H.XPT",
        "NHANES 2013-2014 examined participants; demographic filter and MEC weights.",
    ),
    "nhanes-2013-2014-grip": (
        "MGX_H.XPT",
        "https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/2013/DataFiles/MGX_H.XPT",
        "NHANES 2013-2014 combined handgrip-strength examination.",
    ),
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def weighted_quantiles(values: pd.Series, weights: pd.Series) -> tuple[float, ...]:
    frame = pd.DataFrame({"value": values, "weight": weights}).dropna()
    frame = frame[(frame["weight"] > 0) & np.isfinite(frame["value"])]
    frame = frame.sort_values("value")
    cumulative = frame["weight"].cumsum().to_numpy(dtype=float, copy=True)
    cumulative /= cumulative[-1]
    result = np.interp(
        QUANTILE_PROBABILITIES,
        cumulative,
        frame["value"].to_numpy(dtype=float),
        left=float(frame["value"].iloc[0]),
        right=float(frame["value"].iloc[-1]),
    )
    result[0] = float(frame["value"].iloc[0])
    result[-1] = float(frame["value"].iloc[-1])
    return tuple(round(float(item), 8) for item in result)


def parameter(
    frame: pd.DataFrame,
    *,
    signal_id: str,
    column: str,
    unit: str,
    scale: float,
    source_ids: tuple[str, ...],
    applicability: str,
) -> PopulationParameterPrior:
    usable = frame[[column, "WTMEC2YR"]].dropna().copy()
    usable = usable[(usable["WTMEC2YR"] > 0) & np.isfinite(usable[column])]
    values = usable[column].astype(float) * scale
    weights = usable["WTMEC2YR"].astype(float)
    total_weight = float(weights.sum())
    mean = float(np.dot(values, weights) / total_weight)
    variance = float(np.dot((values - mean) ** 2, weights) / total_weight)
    effective_n = total_weight**2 / float(np.dot(weights, weights))
    quantiles = weighted_quantiles(values, weights)
    return PopulationParameterPrior(
        signal_id=signal_id,
        unit=unit,
        resolution=TimeResolution.DAY,
        distribution=PriorDistribution.EMPIRICAL_QUANTILES,
        mean=round(mean, 8),
        standard_deviation=round(math.sqrt(variance), 8),
        quantile_probabilities=QUANTILE_PROBABILITIES,
        quantile_values=quantiles,
        unweighted_sample_size=len(usable),
        effective_sample_size=round(effective_n, 8),
        lower_bound=quantiles[0],
        upper_bound=quantiles[-1],
        source_reference_ids=source_ids,
        applicability=applicability,
    )


def weighted_complete_case_correlations(
    frame: pd.DataFrame,
    variables: dict[str, tuple[str, float]],
    *,
    source_ids: tuple[str, ...],
    applicability: str,
) -> tuple[PopulationCorrelation, ...]:
    columns = [column for column, _ in variables.values()]
    complete = frame[[*columns, "WTMEC2YR"]].dropna().copy()
    complete = complete[complete["WTMEC2YR"] > 0]
    matrix = np.column_stack([
        complete[column].to_numpy(dtype=float) * scale
        for column, scale in variables.values()
    ])
    weights = complete["WTMEC2YR"].to_numpy(dtype=float, copy=True)
    weights /= weights.sum()
    means = np.sum(matrix * weights[:, None], axis=0)
    centered = matrix - means
    covariance = (centered * weights[:, None]).T @ centered
    standard_deviations = np.sqrt(np.diag(covariance))
    correlation = covariance / np.outer(standard_deviations, standard_deviations)
    signal_ids = list(variables)
    return tuple(
        PopulationCorrelation(
            left_signal_id=signal_ids[left],
            right_signal_id=signal_ids[right],
            coefficient=round(float(correlation[left, right]), 8),
            source_reference_ids=source_ids,
            applicability=(
                f"{applicability} Weighted complete-case Pearson dependency; "
                f"n={len(complete)}. Used as a Gaussian-copula approximation."
            ),
        )
        for left, right in combinations(range(len(signal_ids)), 2)
    )


def source(reference_id: str, population: str) -> PopulationEvidenceSource:
    filename, url, basis = SOURCES[reference_id]
    return PopulationEvidenceSource(
        reference_id=reference_id,
        url=url,
        content_hash=sha256(RAW / filename),
        population=population,
        statistic_basis=basis,
        limitations=(
            "Public cross-sectional U.S. survey data; not an athlete reference and not longitudinal.",
            "MEC weights estimate population distributions; stored standard deviations are population dispersion, not survey-design standard errors.",
        ),
    )


def build_prior(sex_code: int, sex_label: str) -> PopulationPrior:
    demo_j = pd.read_sas(RAW / "DEMO_J.XPT", format="xport")
    bmx_j = pd.read_sas(RAW / "BMX_J.XPT", format="xport")
    dxx_j = pd.read_sas(RAW / "DXX_J.XPT", format="xport")
    recent = demo_j.merge(bmx_j, on="SEQN", how="inner").merge(dxx_j, on="SEQN", how="left")
    recent = recent[
        (recent["RIAGENDR"] == sex_code)
        & recent["RIDAGEYR"].between(20, 39, inclusive="both")
        & (recent["RIDSTATR"] == 2)
    ].copy()

    demo_h = pd.read_sas(RAW / "DEMO_H.XPT", format="xport")
    mgx_h = pd.read_sas(RAW / "MGX_H.XPT", format="xport")
    grip = demo_h.merge(mgx_h, on="SEQN", how="inner")
    grip = grip[
        (grip["RIAGENDR"] == sex_code)
        & grip["RIDAGEYR"].between(20, 39, inclusive="both")
        & (grip["RIDSTATR"] == 2)
    ].copy()

    population = f"U.S. {sex_label} adults aged 20-39 years"
    applicability = (
        f"Population initialization for {population}; general-population reference only."
    )
    sources = tuple(source(reference_id, population) for reference_id in SOURCES)
    anthro_sources = (
        "nhanes-2017-2018-demographics",
        "nhanes-2017-2018-body-measures",
    )
    dxa_sources = (
        "nhanes-2017-2018-demographics",
        "nhanes-2017-2018-dxa",
    )
    grip_sources = (
        "nhanes-2013-2014-demographics",
        "nhanes-2013-2014-grip",
    )
    recent_variables = {
        "stature": ("BMXHT", 1.0),
        "body_mass": ("BMXWT", 1.0),
        "body_mass_index": ("BMXBMI", 1.0),
        "waist_circumference": ("BMXWAIST", 1.0),
        "hip_circumference": ("BMXHIP", 1.0),
        "upper_arm_circumference": ("BMXARMC", 1.0),
        "total_body_bmd": ("DXDTOBMD", 1.0),
        "fat_mass": ("DXDTOFAT", 0.001),
        "lean_mass_excluding_bmc": ("DXDTOLE", 0.001),
        "bone_mineral_content": ("DXDTOBMC", 0.001),
        "body_fat_percentage": ("DXDTOPF", 1.0),
    }
    parameter_specs = {
        "stature": ("BMXHT", "cm", 1.0, anthro_sources),
        "body_mass": ("BMXWT", "kg", 1.0, anthro_sources),
        "body_mass_index": ("BMXBMI", "kg/m2", 1.0, anthro_sources),
        "waist_circumference": ("BMXWAIST", "cm", 1.0, anthro_sources),
        "hip_circumference": ("BMXHIP", "cm", 1.0, anthro_sources),
        "upper_arm_circumference": ("BMXARMC", "cm", 1.0, anthro_sources),
        "total_body_bmd": ("DXDTOBMD", "g/cm2", 1.0, dxa_sources),
        "fat_mass": ("DXDTOFAT", "kg", 0.001, dxa_sources),
        "lean_mass_excluding_bmc": ("DXDTOLE", "kg", 0.001, dxa_sources),
        "bone_mineral_content": ("DXDTOBMC", "kg", 0.001, dxa_sources),
        "body_fat_percentage": ("DXDTOPF", "%", 1.0, dxa_sources),
    }
    parameters = tuple(
        parameter(
            recent,
            signal_id=signal_id,
            column=column,
            unit=unit,
            scale=scale,
            source_ids=source_ids,
            applicability=applicability,
        )
        for signal_id, (column, unit, scale, source_ids) in parameter_specs.items()
    ) + (
        parameter(
            grip,
            signal_id="combined_grip_strength",
            column="MGDCGSZ",
            unit="kg",
            scale=1.0,
            source_ids=grip_sources,
            applicability=(
                f"Grip-strength marginal for {population}; sourced from 2013-2014 "
                "and intentionally left independent of 2017-2018 variables."
            ),
        ),
    )
    correlations = weighted_complete_case_correlations(
        recent,
        recent_variables,
        source_ids=(
            "nhanes-2017-2018-demographics",
            "nhanes-2017-2018-body-measures",
            "nhanes-2017-2018-dxa",
        ),
        applicability=applicability,
    )
    component_frame = recent[
        ["BMXWT", "DXDTOFAT", "DXDTOLE", "DXDTOBMC", "WTMEC2YR"]
    ].dropna()
    residual = (
        component_frame["BMXWT"]
        - component_frame["DXDTOFAT"] * 0.001
        - component_frame["DXDTOLE"] * 0.001
        - component_frame["DXDTOBMC"] * 0.001
    )
    residual_quantiles = weighted_quantiles(residual, component_frame["WTMEC2YR"])
    constraint = LinearPlausibilityConstraint(
        constraint_id="measured-mass-minus-dxa-components",
        unit="kg",
        terms=(
            PlausibilityTerm(signal_id="body_mass", coefficient=1.0),
            PlausibilityTerm(signal_id="fat_mass", coefficient=-1.0),
            PlausibilityTerm(signal_id="lean_mass_excluding_bmc", coefficient=-1.0),
            PlausibilityTerm(signal_id="bone_mineral_content", coefficient=-1.0),
        ),
        lower_bound=math.floor(residual_quantiles[0] * 100) / 100,
        upper_bound=math.ceil(residual_quantiles[-1] * 100) / 100,
        source_reference_ids=(
            "nhanes-2017-2018-demographics",
            "nhanes-2017-2018-body-measures",
            "nhanes-2017-2018-dxa",
        ),
        basis=(
            "Observed full range of measured scale mass minus whole-body DXA fat, "
            f"lean-excluding-BMC, and BMC in the filtered sample; n={len(component_frame)}."
        ),
    )
    return PopulationPrior(
        prior_id=f"nhanes-us-{sex_label}-20-39-v1",
        observed_at=datetime(2020, 2, 1, tzinfo=timezone.utc),
        population=population,
        parameters=parameters,
        correlations=correlations,
        plausibility_constraints=(constraint,),
        sources=sources,
        applicability=applicability,
        limitations=(
            "This is a cross-sectional U.S. general-population prior, not an elite-athlete or combat-performance prior.",
            "Grip strength is from 2013-2014; it has no asserted cross-cycle correlation with the 2017-2018 body-composition variables.",
            "Empirical marginals and a Gaussian-copula approximation do not reconstruct the confidential joint population distribution exactly.",
            "No personal endpoint or longitudinal response is identified by this prior.",
        ),
    )


def main() -> None:
    missing = [filename for filename, _, _ in SOURCES.values() if not (RAW / filename).is_file()]
    if missing:
        raise FileNotFoundError("missing raw NHANES files: " + ", ".join(missing))
    priors = [build_prior(1, "male"), build_prior(2, "female")]
    payload = {
        "schema_version": "nhanes-population-prior-v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "generator": "scripts/reference_data/derive_nhanes_population.py",
        "priors": [item.model_dump(mode="json") for item in priors],
        "prior_hashes": {item.prior_id: item.content_hash for item in priors},
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(OUTPUT), "prior_hashes": payload["prior_hashes"]}, indent=2))


if __name__ == "__main__":
    main()
