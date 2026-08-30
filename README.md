# Frontier Research Harness

A lightweight research environment for Codex. The user gives a goal in natural
language; Codex decides how to investigate it using current evidence, relevant
external scientific models, and reproducible experiment records.

## Active environment

```text
User <-> Codex
          |-- small goal/current-state/research workspace
          |-- scholarly search and retained evidence
          |-- established external scientific models
          |-- unit-checked calculations for 27 physical targets
          `-- immutable inputs, versions, provenance, and raw outputs
```

The active path has no mandatory measurement contract, special frontier-
hypothesis phase, predeclared research protocol, Planner/Reviewer, gate, state
machine, or fixed 24-month strategy search. Hypotheses and possible methods are
created and revised naturally as Codex researches the goal. Effectiveness and
efficiency remain continuing optimization objectives rather than separate
features.

Research starts from the whole-person question and moves into organ, tissue,
cellular, or molecular detail when doing so can change the conclusion. The
active model toolbox exposes established external engines and preserves their
exact runs. A model is used only within its documented context; a successful
run is not automatically a personalized prediction.

The model catalog distinguishes a verified reference run from a research-
callable, target-relevant, or personalized model. These states are never
treated as synonyms. The boxing technical goal remains part of the North Star,
but footage-only technique research uses broad timestamped fight and training
observations instead of an unrelated physiological simulation.

For physical questions, `list_models` can receive the goal targets in scope and
returns compatible models by whole-person, organ, musculoskeletal, tissue, and
cellular Model Layer. A broad synthesis must include a current-turn experiment
from every relevant executable layer, and an experiment cannot be attached to
an incompatible target. The routing is derived during the call and is not a
stored plan or agent state machine.

The default workspace loads only the exact fixed goal, accepted personal
baseline, current state, constraints, hypotheses, research notes, and promising
methods. Evidence and model experiments use separate records and can be loaded
again in later chats.

Literature search supports independent multi-source queries, pagination,
transient-error retries, per-query failure isolation, and DOI/PMID/work-level
deduplication. Search metadata is never treated as read evidence: retained
evidence must include inspected content, the claims actually used,
applicability, limitations, and a content hash. A small plugin hook asks Codex
to continue once when a research tool failed or it tries to stop without
current-turn target-compatible runs across the relevant Model Layers and a
validated mapping from every goal target in scope to retained evidence.
Technical-footage-only
research is exempt from the model call. This one-turn receipt is not stored as
a plan or workflow object, and the hook does not score claims or choose the
research path.

`calculate_target` covers every physical target with bounded formulas, strict
units, formula versions, input hashes, and immutable results. It returns
`INPUT_REQUIRED` rather than inventing missing data and labels arithmetic or
measurement-derived results separately from biological forecasts.

`assess_targets` projects the latest immutable calculations across all 27
physical targets as `TARGET_MET`, `GAP_OBSERVED`, or `MEASUREMENT_REQUIRED`.
It is a live readiness view, not a persisted plan or an adaptation forecast.

OpenSim, Pulse, and FEBio expose typed study contracts in addition to the
low-level registered-engine boundary. The contracts validate workspace-local
input/output artifacts and require an explicit reference or personal-
observation calibration label. Personal OpenSim studies also require a saved
state snapshot; a runtime smoke case cannot silently become a personal study.

Timestamped boxing fight/training observations can be retained through
`save_footage_observation`. Each record preserves the inspected interval,
situation, observed actions, explicit repeated-pattern status, possible drills,
applicability, limitations, and a content hash as primary-source evidence.

The active user-confirmed target is stored in [goal.json](goal.json).

## Chat use

Ask naturally. One message may contain one topic or several, for example:

> 목 힘, 선택반응, 고강도 후 폭발력 저하를 각각 연구하고 서로 충돌하지
> 않는 최적 훈련 방향으로 합쳐줘.

Codex separates the topics internally, researches each with current evidence
and relevant external models, then synthesizes interactions and implications
for the fixed goal. No form, research ID, manual phase, or separate task is
required. The old Kernel, custom simulators, measurement-contract machinery,
frontier workflow, and fixed strategy scripts have been removed.

## Validation

```powershell
uv run python -m unittest discover -s tests -v
```

See [AGENTS.md](AGENTS.md) for invariants, [CONTEXT.md](CONTEXT.md) for active
terms, [docs/BLUEPRINT.md](docs/BLUEPRINT.md) for the architecture, and
[docs/ARTIFACT_POLICY.md](docs/ARTIFACT_POLICY.md) for version-control boundaries.
