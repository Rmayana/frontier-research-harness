# Lean Codex Research Environment

## Purpose

Give Codex the smallest reliable environment needed to research a user-defined
goal well. Scientific judgment stays in Codex; code connects evidence and
external models and preserves reproducible records.

## Active architecture

```text
natural-language goal and updates
              |
              v
            Codex
       /        |         \
small state   evidence   external models
 workspace     search     and exact runs
       \        |         /
        concise retained record
```

The workspace contains only:

- the currently approved fixed goal;
- current state supplied or accepted by the user;
- constraints and important unknowns;
- live hypotheses and promising methods;
- concise research notes;
- retained source records; and
- immutable external-model experiment records.
- immutable unit-checked calculations for the fixed physical targets.

Default reads are section-selective and token-bounded. Accepted local profile
and body-composition snapshots are folded into current state automatically,
with their uncertainty and provenance intact.

## Research behavior

Codex understands the user conversationally and chooses the research route.
It continually seeks more effective and efficient methods. Hypotheses are part
of ordinary reasoning, not a special discovery subsystem. Comparisons,
measurements, or stricter protocols are used when the question actually needs
them, not because the workspace requires them.

Substantial research uses current primary evidence and relevant connected
external scientific models. Investigation proceeds top-down: whole-person
first, then organ, tissue, cellular, or molecular detail where deeper modeling
can alter the answer. Exact model inputs, model/runtime versions, provenance,
raw outputs, and limitations are stored. Model execution success never implies
personal predictive validity.

For physical research, the catalog accepts target IDs and returns compatible
models grouped by Model Layer. Broad research must execute a current-turn,
target-compatible experiment in every relevant executable layer before it can
claim synthesis. This is deterministic routing metadata inside the existing
receipt, not a planner or persisted workflow. It prevents an easy cellular
model from substituting for whole-person, organ, musculoskeletal, or tissue
questions while Codex still chooses the scientific question and model.

The boxing technical goal is an explicit exception to model execution: Codex
uses broad primary fight and training footage, retains timestamped
observations, separates repeated technique from opponent-specific variation,
and converts the evidence into drills. A physiological model is not called for
a footage-only question.

Footage observations use a strict primary-source contract carrying the exact
interval, athlete and context, observed actions, situational conditions,
explicit repeated-pattern status, possible drills, applicability, limitations,
and a content hash. A single clip is never promoted to a repeated pattern by
the storage layer.

Model inventory separates installation and reference-run verification from
research callability, target relevance, and personal calibration. A smoke test
never claims the latter three. Deterministic target calculations preserve the
exact input, units, formula version, output, and hash while labeling the result
as arithmetic or measurement-derived rather than a longitudinal forecast.
The latest calculations may be projected into a non-persistent measurement-
readiness view; missing observations remain explicit rather than being filled
with reference values.

The highest-priority OpenSim, Pulse, and FEBio paths add engine-specific typed
study inputs above the generic registered-runtime bridge. They validate
workspace-local artifacts and calibration labels while leaving question choice
and result interpretation to Codex. Deterministic normalizers expose bounded
engine observables plus the original receipt: they parse neither convergence
nor simulated peaks as personal efficacy, injury risk, or adaptation.

A Personal Combat Athlete Digital Twin may federate these external models
through strict exchange contracts. Every exchanged value carries units, time
resolution, uncertainty, calibration level, applicability, and immutable
provenance. Reference-boundary or population-prior inputs fail closed if a
caller attempts to label their output as a personal endpoint prediction. The
twin supplies state estimates and research constraints; Codex still chooses
scientific questions and strategies, and the twin never activates an
intervention.

Candidate discovery is paginated and fault-isolated across queries. Codex
decides when useful coverage has plateaued, then fetches selected primary
records and retains only evidence actually used. Retained evidence includes the
inspected payload, claims used, applicability, limitations, and a content hash;
metadata-only scholarly records are rejected.

A deterministic execution receipt notices unresolved tool failures, duplicate
fetches, omitted Model Layers, model-to-target mismatches, invalid persistence,
or explicit goal targets that were not mapped to retained evidence. It permits
one bounded continuation. A whole-goal receipt covers every structured physical
target and the technical goal; a narrow receipt is allowed only for a declared
target subset. The receipt is validated during `save_research` but is not
persisted as a workflow object. It does not judge scientific validity, rank
hypotheses, or prescribe the next scientific action.

## Deliberately absent

These components are not part of the repository:

- Harness Kernel control flow and StateLedger orchestration;
- custom whole-body and long-horizon simulators;
- mandatory measurement contracts;
- frontier-candidate generation/promotion schemas;
- predeclared Protocol -> Result -> Synthesis lineage; and
- fixed 24-month strategy screening.

Several research topics in one message form a temporary portfolio. Codex
researches each topic, then integrates shared mechanisms, conflicts, and
trade-offs into one goal-level answer without creating a workflow object.

## Authority

Codex may research, search, calculate, run passive external models, compare
results, diagnose, and revise. Explicit user approval is required before a
real-world strategy is activated, the fixed goal changes, money is spent, an
external action is booked, external data is mutated, or medical/drug/supplement
action is taken.

## Engineering

When extending the environment, first inspect strong maintained open-source
implementations and scientific model adapters. Reuse compatible code when its
license and fit are clear. Add a dependency or subsystem only when it removes a
demonstrated bottleneck in the active Codex loop.
