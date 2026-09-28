# Evidence and personalization

## Literature

Search independent query families across complementary sources and follow
`next_queries` while new pages still add decision-relevant records. Search
results are candidate metadata, never read evidence. Prefer current systematic
evidence and guidelines for the landscape, then inspect primary studies needed
for methods, heterogeneity, adverse effects, boundary conditions, or competing
explanations.

Fetch selected records. PubMed fetch automatically attempts linked PMC open
full text. Prefer full text when methods, subgroup applicability, outcome
definitions, or bias details can change the conclusion; an abstract may support
only an abstract-bounded claim. Never silently infer unavailable methods or
results.

For scholarly `save_evidence`, provide:

- the returned `fetch_id`, which supplies the preserved payload, source, URL,
  content level, and identifier automatically (or an exact `fetched_record`
  for externally obtained content); add the title if absent from the response;
- one or more fixed-goal `target_ids`;
- bounded `retained_claims`, applicability, and limitations;
- short `evidence_passages`, each with an exact excerpt, a locator, and one
  `supports_claim` string exactly matching a retained claim; and
- `quality_appraisal`: a concise source-bounded assessment in free text, or
  structured source type, population, methods, results, directness, and limits.

Fetching preserves a source response, not a scientific conclusion. Inspect it
before attaching claims. Do not resend or reconstruct a cached payload, and do
not mistake a filled appraisal or a valid citation for a sound interpretation.

Do not assign a generic numeric quality score. Compare study design,
population, intervention and comparator, outcomes, precision, consistency,
directness, bias, and applicability in scientific reasoning. Store excerpts
only to ground retained claims; do not reproduce long copyrighted passages in
the answer.

For the boxing technical goal, primary fight and training footage is required.
Use timestamped `save_footage_observation` records, inspect multiple opponents
and contexts, and use exact-label comparison only as a retrieval aid. Codex
must judge semantic similarity, opponent-specific variation, and transfer.
Generic boxing literature cannot substitute for the named athlete's actions.

## Personal observations

Personal observations are not a prerequisite for scientific research,
hypothesis design, reference simulation, or conditional strategy comparison.
Before they exist, use current human evidence, qualified population priors,
physical laws, and validated mechanistic models without presenting their output
as a personal forecast. Add personalization progressively as comparable data
accumulate.

Do not demand a comprehensive measurement contract. Ask for or retain only
observations likely to change the current decision. Use
`save_personal_observations` for numerical data with timezone, goal links,
metric, value, unit, protocol, source type, instrument when relevant,
uncertainty when known, and non-empty provenance.

Use `list_personal_observations` before discussing individual response.
Compare trends only within the same protocol hash, which fixes target links,
metric, unit, protocol, and instrument. A first-to-latest delta is descriptive;
it does not identify intervention effect, measurement validity, or a future
response. Preserve missing baselines, incompatible protocols, sparse series,
confounding, and measurement error as unknowns.

For genuine personal prediction, require repeated comparable observations and
a model validated for the endpoint, horizon, population, and calibration level.
Otherwise give conditional scenarios or decision thresholds, not a personal
success probability.

Use `digital_twin` only when its qualified model federation can change the
answer. `status` reports whether observations, projections, and prediction-error
records exist; `describe` loads only the required contract. `build_reference`
accepts a source-qualified human prior, exact personal observation IDs and
signal mappings, or both. `sample_population` is a reproducible uncertainty
ensemble, not a set of predicted people. `run` accepts qualified external-model
receipts, native engine bindings, and independently validated evidence-response
models. Every response coefficient must come from inspected sources and carry
validation evidence; never infer missing coefficients from intuition.
`run_multirate` only orders qualified model windows and carries declared state;
it does not create a biological transition between them. `compare` performs
side-by-side arithmetic, and `evaluate` records projected-versus-observed error
against a later observation. None changes model parameters or claims personal
calibration. Machine-learning calibration requires adequate repeated personal
data and a separately justified validation method.

## Retained statements

Use `current_understanding` for the current causal explanation and strategy in
your own words. Replace it as understanding changes; earlier versions can be
loaded with `history_limit`. Lists of notes and hypotheses preserve historical
observations and are not an authoritative list of still-accepted conclusions.

Items in `hypotheses`, `research_notes`, and `promising_methods` may be concise
plain strings. Use the structured form when an explicit epistemic label or
receipt is useful:

```json
{
  "statement": "one concise bounded statement",
  "support_status": "SUPPORTED | USER_OBSERVATION | MODEL_BOUND | MEASUREMENT_DERIVED | HYPOTHESIS | INFERENCE | UNKNOWN",
  "target_ids": ["optional compatible goal or benchmark IDs"],
  "evidence_ids": [],
  "experiment_ids": [],
  "calculation_ids": [],
  "observation_ids": []
}
```

`SUPPORTED`, `USER_OBSERVATION`, `MODEL_BOUND`, and `MEASUREMENT_DERIVED`
require their matching receipt arrays. Hypotheses, inferences, and unknowns may
remain plain or have no receipt. When target IDs are supplied, receipts must be
compatible with those targets.

When reusing recorded experiments, identify them explicitly as prior work. For
the current request, retrieve only experiments created after the request began or
load a deliberate set of experiment IDs. Never present the accumulated database
as though it were produced by the current research.
