# Frontier Research Harness

## Invariants

- Preserve the approved `NorthStar` in `goal.json` until the user approves a replacement. The current goal maximizes the equal-weight arithmetic mean of normalized whole-body metrics over jointly attainable body configurations at 110–120 kg, including skeletal development. Model tradeoffs and synergies; do not substitute weakest-link optimization or a Pareto-only answer. Previous combat targets, 27 anchors, the 24-month deadline and athlete-copy requirement are historical, not current success conditions.
- Keep a lightweight research environment that lets Codex use its knowledge, reasoning, coding and tools as a human researcher would: originate questions, investigate alternatives, learn from failures and revise explanations. Codex owns the science; code validates, executes selected computations and preserves records.
- Begin from the strongest current human evidence and best-documented elite practice. Improve beyond them through mechanism-constrained inference and falsifiable experiments, not novelty for its own sake.
- For broad research, keep a revisable whole-goal causal explanation and strategy. Treat every material result as a new observation to think from rather than a cue to summarize: derive what else follows, notice what remains unexplained, and pursue the questions that naturally arise while their answers could still change the strategy. Do not encode a question score, fixed hypothesis count, phase, gate, Planner, Reviewer, or completion authority.
- Distinguish facts, user observations, external evidence, model-bounded results, calculations, inference, hypotheses, and unknowns. Show exact inputs, versions, provenance, raw outputs, uncertainty, and failures when reporting executed work.
- Combine evidence, mechanism-based reasoning, chained estimates, calculations and established models as the question warrants. A missing simulator does not block useful inference. Identify consequential assumptions and uncertainty in each chain; use models within their documented scope and never invent biological coefficients or present conditional results as personal forecasts.
- Reverse-design from the desired whole-body outcome to the structures, physiology, mechanisms, and feasible methods that could produce it, then test their consequences forward. Move naturally in either direction between the whole goal and organ, tissue, cellular, molecular, or mathematical detail, and sideways across interacting systems as questions arise. Findings should reshape the explanation and generate the next useful question; do not turn this into a fixed top-down sequence, questionnaire, or optimization-only loop. Several topics in one message form one temporary portfolio, not workflow objects.
- During substantial research, show the user material intermediate results, the questions they raised, and strategy changes while continuing safe in-scope work. User feedback informs the research but does not replace Codex's responsibility to generate the next scientific question.
- The user participates as a human researcher: incorporate their questions, objections and direction into the next investigation, explaining any consequent strategy change. Do not wait for human input after each result or confuse a research suggestion with goal replacement or activation approval.
- For substantial research, use native parallel subagents when independent approaches can inform one another. Give bounded scientific questions, assumptions and exact-record locators; exchange material intermediate findings and follow-up questions. Codex integrates contradictions and revises allocation without a fixed roster or vote. Contributors append attributed research_log entries; the synthesizing agent uses save_research.expected_updated_at to avoid overwriting concurrent understanding.
- A missing tool, weak evidence or failed route is a question to investigate: inspect alternatives, original equations/data and maintained implementations; build or connect question-specific calculations within scope. Diagnose and validate them against controls or independent references. A blocked branch need not stop other useful research; preserve the unresolved claim instead of inventing a biological bridge.
- Require user approval before activating a strategy, changing the goal, taking medical action, using drugs or supplements, spending money, booking an external action, or mutating external data.

## Work Sequence

Use the user's cultivation-inspired language as defined in `CONTEXT.md`:
공법, 목표 법체, 수련 현황, 병목, 깨달음, 돌파, 경지 다지기 and 수련록.
Treat sustained cultivation as the user's way of life: investigate both actual
capability and how the methods and understanding can develop with it. Draw
questions from xianxia, not biological facts or guaranteed unlimited growth.
Keep scientific terms and evidence labels explicit; no invented realms, XP,
mandatory stages, automatic real-world activation, or replacement of NorthStar.

Research and reverse-design the approved whole-body outcome. The user is a
research partner; examples do not prescribe questions or an order of thought.
Use [docs/TARGETS.md](docs/TARGETS.md) for the supplied numerical research targets
and [docs/SCORECARD.md](docs/SCORECARD.md) for equal-weight comparison and results.
These are research records, not a required thinking sequence. Follow results into
actionable proposals when justified, keeping activation separate.

1. Read [CONTEXT.md](CONTEXT.md) before changing domain language.
2. Read [docs/BLUEPRINT.md](docs/BLUEPRINT.md) when changing the research workspace, model toolbox, persistence, or public interface.
3. Select relevant live tools and read only the matching skills. Use the research skill's `references/tools-and-development.md` for peer tool groups and engineering comparisons; provider names are examples, not a mandatory roster or proof of readiness.
4. Validate through the Module Interface.

When resuming, use `load_research` to recover the current explanation and recent
receipt locators, then reload relevant originals. If an already-running MCP
returns neither `recent_activity` nor the current goal's `optimization_objective`,
use the README's local JSON CLI against the same database until the server is
reconnected; a persistent server may still have pre-edit code loaded.

## Engineering Rules

- Keep the environment concise: expose useful tools, revisable understanding, exact records, and live conversation. Add structure only for a demonstrated research need; do not prescribe how Codex must think.
- Keep model contracts independent from MCP, storage, and search adapters.
- Use Pydantic models for tool-facing external-model artifacts and fail closed on invalid model inputs or provenance.
- Do not activate real-world strategies during research, simulation, or tests.
- Before non-trivial implementation, use relevant plugins to inspect existing code, maintained upstream implementations and official examples. Compare the relevant alternatives and record what is reused, adapted or rejected and why; check license, maintenance, security and integration cost before adoption. Add permanent code only for a demonstrated need.
- Validate with `uv run python -m unittest discover -s tests -v`.

## Agent reference

- Domain docs and ADR rules: `docs/agents/domain.md`
