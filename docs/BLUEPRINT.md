# Codex-led scientific research environment

## Purpose

Keep the environment light enough for Codex to use its knowledge, reasoning,
coding and tools as a human researcher would. Expose useful context, evidence,
observations, models and recoverable records. Codex combines mechanism-based
reasoning, chained estimates and question-specific calculations; a complete
simulation model is not a prerequisite for useful research.

## Authority boundary

Codex owns:

- question and hypothesis generation;
- evidence and model selection;
- experimental contrast and uncertainty analysis;
- interpretation, causal diagnosis, cross-target synthesis, and strategy
  revision; and
- the judgment that another investigation is or is not useful.

Code owns:

- schema, unit, compatibility, horizon, calibration, and provenance checks;
- the external engine's own input and execution checks; and
- storage and retrieval of retained literature, observations and research notes.

Codex writes question-specific calculations and comparisons when needed, using
ordinary files for code, inputs and raw results.

Code must not rank questions, choose the next experiment, invent a strategy
score, declare research complete, or fabricate missing biological behavior.
The user-approved equal-weight mean of normalized body metrics is an explicit
optimization objective: code may calculate it and execute Codex-selected searches
through qualified models. It does not determine the research agenda or establish
that a model-bounded optimum is the absolute human maximum.

## Active components

1. **Goal workspace** — fixed North Star, selected current state, constraints,
   revisable free-text current understanding, hypotheses, promising methods,
   and concise durable notes. Replacing the understanding preserves its history.
2. **Goal Research Map** — historical passive links among combat tasks,
   capacities, diagnostic systems and observations. It does not define the
   current whole-body objective or require coverage of its old categories.
3. **Evidence layer** — multi-source discovery, record/full-text retrieval,
   claim-linked evidence retention, and source-bounded appraisal.
4. **Observation layer** — immutable protocol-aware personal measurements and
   descriptive comparable series.
5. **External models** — installed engines, necessary file-format helpers and a
   [short usage guide](EXTERNAL_MODELS.md). Codex creates inputs and experiment
   scripts when needed and preserves useful raw files. No experiment registration,
   shared calculator, graph, population sampler or simulator API is required.
6. **Joint research log** — optional free-text contributions and reply links,
   separate from verified evidence, observations and activation authority.

Specialist plugins extend these peer capabilities directly. Gene manipulation
and drug discovery are separate tool groups alongside evidence, observations,
simulation, analysis and experiments; they do not define phases or fallback
levels. Follow the skill's [tool guide](../plugins/frontier-science-model/skills/goal-research/references/tools-and-development.md)
when selecting them. No new broker, registry or per-provider store is required.

Default reads are section-selective and byte-bounded. Internal IDs and schemas
stay out of ordinary conversation until needed for execution or reproducibility.
Default `load_research` restores the approved objective, reverse-design intent,
artifact paths and action boundary as well as current understanding. Its computed
`recent_activity` section contains chronological experiment, retained-evidence,
research-entry and simulation-request locators with exact reload calls. It is
read-only and does not rank results, generate questions, or promote notes to evidence.
The host Codex model/tool loop performs the ongoing reasoning; this workspace
supports resumption and does not introduce a second autonomous scheduler.
An opt-in foreground operation adapter can own a native Codex goal, retain
transport events and human steering, and enforce explicitly supplied resource
limits. It never issues synthetic continuation turns or judges science. See
[ADR 0005](adr/0005-native-research-operation.md) and [RUNNER.md](RUNNER.md).
Evidence and observations may link to the approved goal ID before a fixed list
of subtargets exists. Validation uses the workspace's saved goal, not a different
goal read from a global file. Model-scope checks still apply to model-bound claims.

Keep the environment small. Codex chooses its own research methods and may use
question-specific code; no added agent organization or scientific phase is
required. The ordinary chat carries intermediate findings and user questions.
Native parallel researchers can pursue independent approaches and exchange
intermediate findings. Attributed append-only contributions survive synthesis;
the synthesis writer uses an expected timestamp and reconciles conflicts.
The human researcher may challenge results and redirect work without becoming
a required approval gate for every next investigation.

The JSON CLI uses the same Module Interface as MCP. Environment inspection
separates configured sources, local runtime discovery, untested network access
and host tool exposure. Fetched content includes reference and linked-material
locators without marking those links as read evidence. Existing MCP SDK and model
adapters are reused; the laboratory adds no solver, question generator or planner.

The Module Interface has three explicit layers. `research_tool_contracts` owns
transport-neutral public schemas, `research_tool_dispatch` maps validated tool
calls to the workspace facade, and the MCP/JSON CLI adapters translate transport
input and output only. The workspace facade keeps its stable import path and
composes separate core persistence, evidence, observation, audit, model, and
experiment-operation modules. These are engineering boundaries; they do not add
scientific phases, workflow authority, or a second source of research state.

## Scientific behavior

Broad research begins from the strongest current human evidence and documented
elite practice. Codex keeps a revisable whole-goal causal explanation and
strategy. Every source, observation, calculation, and model result becomes a
new observation to think from, not a cue to finish and summarize. Codex
integrates its consequences, derives newly calculable or bounded quantities,
and notices what remains unexplained. The resulting questions lead naturally
to mechanism-constrained hypotheses and the smallest qualified investigations
able to change the strategy.

This repeats naturally while more available work can change the decision. It
is not encoded as phases, fixed counts, a question-value formula, or a lifecycle
object. Several topics in one request form a temporary portfolio and are
synthesized back into the single North Star.

Research reverse-designs the desired whole-body outcome into candidate structures,
physiology, mechanisms, and feasible methods, then tests the consequences forward.
Codex moves naturally between whole-person synthesis and organ, tissue, cellular,
molecular, or mathematical detail, and across interacting systems. The question
and evidence determine the useful resolution and next investigation; broad-to-fine
and fine-to-broad reasoning have no prescribed order. New findings can revise the
causal explanation, model assumptions, candidate combinations, and realization
methods. Numerical optimization is one instrument of this research, not its entire
loop. The target and score tables are linked from `goal.json`, with uncomputed
results and unresolved definitions explicit.

Substantial research can unfold as a live conversation. Codex surfaces material
intermediate results, their concise scientific implications, questions that
actually emerged, and strategy revisions while continuing safe in-scope work.
The user's challenges and observations improve the research but do not replace
Codex's responsibility for the next question.

## Direct external-model use

An external model is usable only inside its documented endpoint, population,
inputs, units, calibration level, horizon, validation evidence, and runtime
version. A successful run is not evidence outside that scope.

Codex may infer relationships from existing knowledge, connect model outputs,
repeat calculations with updated state and history, and write question-specific
analyses. Explain assumptions and test consequential connections; no predeclared
graph, qualification packet, reference-body object, time-window plan or universal
response equation is required. External adapters retain their actual input and
unit checks. Preserve code and exact inputs/results when computations are run.

Reference-data JSON and existing experiment databases are preserved as historical
files. No new experiment database or registry is required. Use each engine directly
and create experiment files only when needed. See [EXTERNAL_MODELS.md](EXTERNAL_MODELS.md)
and [ADR 0007](adr/0007-direct-external-models.md).

## Retained records

Evidence records preserve inspected content, bounded claims, located passages,
applicability, limitations, identifiers, and content hashes. Experiment records
preserve question, full input, model/runtime identity and version, provenance,
raw output, output hash, uncertainty, failures, and optional interpretation.
Personal observations preserve time, unit, protocol, instrument, uncertainty,
and provenance.

Exploratory hypotheses and inferences may remain plain language. Strong labels
such as evidence-supported, user-observed, model-bounded, or
measurement-derived require matching receipts.

## Deliberately absent

- Planner, Reviewer, StateLedger, phase, gate, or stop hook;
- fixed question scoring or mandatory hypothesis counts;
- mandatory measurement contracts or predeclared workflow forms;
- fixed-target calculators or coverage audits in the active research surface;
- repository-invented biological coefficients, adaptation endpoints, or
  whole-body longitudinal simulators;
- coverage or model-layer completion requirements; and
- automatic real-world strategy activation.

## Engineering

Literature fetches retain their exact responses automatically. A fetch ID lets
Codex attach claims and a natural-language or structured appraisal without
resending the source payload; fetching alone does not establish read evidence.
New model executions write the files selected for that experiment. Preserve useful
engine diagnostics, including failures. Historical failed experiments cannot support
successful model-result claims.
Earlier experiment rows without a status migrate as successful legacy receipts.

Keep model contracts independent from MCP, storage, and search adapters. Use
typed validation for tool-facing scientific artifacts and fail closed on
invalid units, model compatibility, calibration, horizon, or provenance.
Inspect maintained open-source designs and official model adapters before
adding a subsystem, but add a dependency only when it removes a demonstrated
bottleneck in the active Codex loop.
Compare relevant existing implementations and record reuse/adaptation/rejection
reasons in the change report. During real use, improve observed friction in small
increments. Evaluate research behavior and actual resource use separately from
format checks, test counts or installed tool counts; see
[research environment evaluation](RESEARCH_ENVIRONMENT_EVAL.md).
