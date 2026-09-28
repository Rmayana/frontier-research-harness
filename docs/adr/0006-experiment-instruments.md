# ADR 0006: Let Codex connect experiment instruments

Status: Superseded by ADR 0007 after the user requested direct external-model use.

## Context

The user wants scientific instruments and Codex's intelligent experiment design.
The additional graph, model-qualification, twin-state, time-window and fixed-point
frameworks duplicated reasoning and required large declarations before a calculation.
This decision applies ADR 0004's lean-environment principle to those newer layers.

## Decision

Remove simulation_lab and digital_twin execution surfaces and their orchestration
implementations. Retain established external adapters, direct run_model execution,
unit-aware arithmetic, fitting, data access, observation records and comparisons.
Separate the existing population data/sampler from twin execution. Keep a small
read-only reader for historical simulator records without the old executors.

Codex can infer relationships from knowledge, connect tools, write question-specific
analyses, repeat calculations and choose numerical solvers. Preserve the code,
inputs, provenance and raw results; scientific judgment belongs to Codex.
No new solver, framework, dependency or upstream implementation is needed: the
existing direct adapters and numerical workbench already supply these instruments.

## Consequences

Old graph/twin execution callers must switch to direct tools; old data is retained.
There is no shared automatic state-carry or convergence service. Those computations
are selected and implemented for the question when needed. Numerical validity and
scientific applicability remain distinct. Engine-specific validation stays intact.
