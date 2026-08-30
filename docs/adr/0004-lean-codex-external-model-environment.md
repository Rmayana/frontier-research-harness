# ADR 0004: Keep the active research environment lean

Status: Accepted

## Context

The repository accumulated a control Kernel, measurement machinery, custom
whole-body simulators, a frontier-discovery subsystem, prospective protocol
lineage, and a fixed-horizon strategy screen. These structures increased
context, validation, and maintenance cost while constraining how Codex reasoned
before the user had even supplied the next research goal. Some were also loaded
as import side effects despite not appearing in the public tool surface.

The user wants Codex's own information processing and intelligence to remain
central, with established external scientific models available for deeper
top-down research.

## Decision

The active plugin consists only of a token-bounded research workspace,
scholarly evidence access, external scientific model adapters, and immutable
experiment records. Codex selects the questions, hypotheses, evidence, models,
interpretations, and revisions in response to the user's natural language.

There is no mandatory measurement contract, special frontier-hypothesis stage,
predeclared protocol lineage, Planner/Reviewer, gate, state machine, or fixed
24-month strategy engine. Custom repository-built whole-body simulators and the
Harness Kernel are not imported by the active plugin.

Legacy modules and generated research records are removed. Shared external-
model validation primitives remain independent. Engineering work may reuse
suitable open-source designs after checking license and fit, but no framework
is added without a demonstrated active-loop need.

## Consequences

- Codex can research each new goal flexibly instead of filling predetermined
  artifacts.
- Active context and import cost no longer include the large legacy workflow.
- Established external models remain reproducible and context-bounded rather
  than being presented as personalized truth.
- Multiple topics can be requested in ordinary chat and integrated without a
  persistent workflow object.
