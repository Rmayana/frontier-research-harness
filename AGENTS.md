# Frontier Research Harness

## Invariants

- Preserve the currently stored `NorthStar` and success conditions until the user approves a replacement. Keep internal goal enums out of normal conversation.
- Codex owns research planning, evidence selection, hypotheses, experiment design, model choice, interpretation, diagnosis, and revision.
- Distinguish facts, user observations, external evidence, inference, hypotheses, and unknowns.
- Research top-down from the whole-person question into organs, tissues, cells, or molecules only when deeper detail can change the decision. Never infer whole-body completeness from a coverage inventory.
- Compare meaningful alternatives when the question requires it; no dedicated Baseline artifact is required.
- Require user approval before activating a strategy, spending money, booking an external action, taking medical action, using drugs or supplements, mutating external data, or changing the fixed goal.
- Treat external-model output and isolated observations as context-bounded evidence, not proof of personal efficacy.
- The plugin validates external-model inputs and preserves exact inputs, versions, provenance, and raw outputs; it does not impose a measurement contract, Planner, Reviewer, Gate, phase, state machine, frontier-discovery module, or fixed-horizon strategy engine.
- Several research topics in one user message are one temporary portfolio: research each, then synthesize interactions and goal-level implications without creating workflow objects.

## Work Sequence

1. Read [CONTEXT.md](CONTEXT.md) before changing domain language.
2. Read [docs/BLUEPRINT.md](docs/BLUEPRINT.md) when changing the research workspace, model toolbox, persistence, or public interface.
3. Keep scientific judgment in Codex; deterministic code should validate calculations and preserve records.
4. Validate through the Module Interface.

## Engineering Rules

- Keep model contracts independent from MCP, storage, and search adapters.
- Use Pydantic models for tool-facing external-model artifacts and fail closed on invalid model inputs or provenance.
- Do not activate real-world strategies during research, simulation, or tests.
- When implementing, inspect suitable established open-source designs and external model adapters first. Reuse or adapt them only when their license, maintenance state, and fit are clear; do not add a framework merely because it exists.
- Validate with `uv run python -m unittest discover -s tests -v`.

## Agent reference

- Domain docs and ADR rules: `docs/agents/domain.md`
