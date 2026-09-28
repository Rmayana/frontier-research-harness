# Frontier Research Harness

A lightweight research environment for Codex. The user gives a goal in natural
language; Codex investigates like a human researcher, combining knowledge,
evidence, chained estimates, calculations and tools to revise its explanation.
The repository supplies access, execution and recoverable records.

Use the environment on real questions and improve observed friction in small
increments. Specialist plugins, including separate gene-manipulation and
drug-discovery tool groups, are described in the research skill's
[optional tool guide](plugins/frontier-science-model/skills/goal-research/references/tools-and-development.md).
They are peer tools selected for the question, not a required workflow.

## Start here for human and AI reviewers

This repository publishes the research environment, not personal research data.
Read [AGENTS.md](AGENTS.md), [CONTEXT.md](CONTEXT.md), the current
[blueprint](docs/BLUEPRINT.md), and the [research skill](plugins/frontier-science-model/skills/goal-research/SKILL.md)
for the intended behavior. [ADR 0007](docs/adr/0007-direct-external-models.md)
describes direct model use; older decisions and archived examples may be superseded.

The working goal and target tables describe research objectives, not demonstrated
human outcomes. Personal observations, research databases, credentials and installed
scientific runtimes are excluded. The plugin's `.mcp.json` contains local deployment
paths: configure `cwd` and the Python executable for your own checkout before use.
Optional vendor source dependencies can be obtained with `git submodule update --init`.

Current baseline (2026-09-28): 136 local unit tests passed; skill/plugin format
validation passed. This is not evidence of improved scientific intelligence or
cross-machine runtime readiness. See [evaluation criteria](docs/RESEARCH_ENVIRONMENT_EVAL.md)
and the [external model guide](docs/EXTERNAL_MODELS.md) for limits and optional tools.

Improve from actual use: describe the observed problem or missing capability,
inspect relevant existing implementations and plugins, make one useful bounded
change, and verify it. Report evidence, changed behavior and remaining uncertainty.
Keep the environment light and preserve the approved goal and useful records.

## Core architecture

The public Module Interface is transport independent. `research_tool_contracts`
defines the shared tool schemas and `research_tool_dispatch` invokes the stable
`FrontierScienceWorkspace` facade. The MCP server and JSON CLI only translate
their respective transport inputs and outputs.

The workspace facade is implemented by responsibility-specific internal modules:

| Module | Responsibility |
| --- | --- |
| `_workspace_core` | SQLite lifecycle, goal workspace, resumption, and retained-record reads |
| `_workspace_evidence` | literature discovery, evidence retention, and footage records |
| `_workspace_observations` | personal observations |
| `_workspace_audit` | coverage and integrity audits plus goal/model identifier validation |
| `_workspace_operations` | research log, environment information and historical record reads |

Callers continue to import `FrontierScienceWorkspace` from
`adapters.frontier_science_workspace`; persistence, evidence, observations, and
historical record reads remain separate implementation modules. External models
are run directly as described below.

### Research tools and local fallback

`inspect_environment` shows configured evidence sources, the model guide
and the local entrypoint. It deliberately reports network access as
untested and cannot certify which tools a host has exposed. The local JSON CLI
uses the same dispatcher as MCP; it is available if a conversation has not loaded
the plugin's tools.

On this Windows workspace, the plugin uses `.venv-research/Scripts/python.exe`
and an absolute workspace `cwd`, so a cached plugin cannot resolve its database
or Python environment relative to the plugin cache. A relocated checkout needs
its MCP command and cwd updated. For a fresh environment:

```powershell
$env:UV_CACHE_DIR = Join-Path (Get-Location) '.uv-cache'
$env:UV_PROJECT_ENVIRONMENT = Join-Path (Get-Location) '.venv-research'
uv sync --locked
uv run python -m unittest discover -s tests -v
```

Optional scientific runtimes are discovered separately. The existing OpenSim
4.6 installation was preserved in the new environment and smoke-tested; it is
not a dependency supplied by `uv sync`. Recreating this environment requires
installing the appropriate OpenSim package separately when that engine is needed.

```powershell
# Inspect schemas without touching the personal database.
& .venv-research/Scripts/python.exe -X utf8 -m frontier_research_harness.adapters.research_cli tools
# Read JSON arguments from a file; no quoting or embedded Python needed.
& .venv-research/Scripts/python.exe -X utf8 -m frontier_research_harness.adapters.research_cli search_literature --input queries.json
```

`queries.json` uses `{"queries":[{"source":"pubmed","query":"your research query"}],"page_size":10}`.
The same route supports every advertised tool, including `load_research`,
`fetch_literature` and `research_log`. `--database` selects an isolated
database for engineering tests. Tool failures return a nonzero CLI exit code.

Resume research with `load_research`: its default response includes the approved
objective, reverse-design intent, target/score table paths, current understanding,
and `recent_activity`. Activity previews link to exact saved results; they are
chronological records, not recommendations or new findings. Explicit `sections`
and `recent_items` keep context bounded. Codex interprets the results, chooses the
next useful question/tool, and saves a revised understanding when appropriate.
The existing host agent loop executes those choices; no second scheduler or
fixed scientific workflow is installed by this project.
An already-running MCP process can retain old Python code. If default
`load_research` lacks `recent_activity` or the current objective, use the local CLI
against the same database until the host reconnects the server. Editing source
does not hot-reload an existing MCP connection.

The installed research skill is also a separate cached copy. After changing the
plugin, use Plugin Creator's cachebuster/update flow and
`codex plugin add frontier-science-model@frontier-research-local`; use a new chat
to pick up the updated skill and tools. Verify source/cache contents rather than
assuming a source edit updated the installed copy.

### External models

Use the [short external-model guide](docs/EXTERNAL_MODELS.md). Codex writes input
files and analysis code when the question requires them, then calls the installed
engine's Python API or executable. Keep useful code, inputs and raw results as files.
There is no simulator tool, mandatory experiment template, shared calculator,
dataset registry or new experiment database. Existing research data is preserved.

Literature search, personal observations, research notes and goal continuity remain
available through the Module Interface. Its bounded original-record reader can
also read old experiment records; the old execution APIs have been removed.

`research_log` optionally appends user/Codex contributions and plan drafts with
free labels and reply links; list pagination uses `after_sequence`. It does not
prescribe questions, assign evidential support or authorize a routine. The current
causal explanation remains in `current_understanding`, with its existing history.
Fetched literature now includes navigation to cited records and linked materials;
those links have not themselves been fetched or verified.

Live engineering acceptance (writes only test records under `.scratch`):

```powershell
& .venv-research/Scripts/python.exe -X utf8 scripts/validate_research_lab.py --engine --mcp
# Also check public scholarly endpoints when network access is available:
& .venv-research/Scripts/python.exe -X utf8 scripts/validate_research_lab.py --online --mcp
```

These checks demonstrate research-tool transport, not autonomous research
quality or a validated personal combat-body simulation. The actual explanation
of combat capability remains open to evidence and discussion with the user.

```text
approved North Star
       |
       v
     Codex  <------ evidence and personal observations
       |
       +---------- qualified external models
       |                 |
       |                 v
       +-------- question-specific code and experiment files
       |
       v
questions -> hypotheses -> experiments -> interpretation -> revised strategy
```

The governing goal in [goal.json](goal.json) is the whole-body configuration at
110–120 kg that maximizes the equal-weight mean of normalized metrics, including
skeletal development. [Numerical research targets](docs/TARGETS.md) preserve the
user-supplied table; [the score table](docs/SCORECARD.md) records comparison rules
and uncomputed results. The former seven combat targets and 27 anchors are
historical, not current requirements.

For broad research Codex starts from the strongest current evidence and
best-documented elite practice, maintains a revisable whole-goal strategy, and
uses every result as a new observation that changes its causal understanding.
It derives newly available quantities, follows unexplained implications and
promising method combinations, and lets those findings naturally produce the
next question, hypothesis, and discriminating investigation. No question score,
fixed hypothesis count, Planner, Reviewer, phase, gate, or completion state is
encoded in the repository.

Codex reverse-designs the desired outcome into structures, physiology, mechanisms,
and feasible methods and tests their consequences forward. It moves naturally
between broad synthesis and fine detail, and across interacting systems as results
raise questions, without a prescribed order. Numerical optimization is one tool
within this research. Combat remains an application of the whole-body goal.
Codex can replace `current_understanding` with concise free text
as its explanation changes; `load_research(history_limit=...)` retrieves earlier
versions. Notes remain available as historical observations, not a list of
currently accepted conclusions.

## What each part does

| Part | Accepts | Returns | Does not do |
| --- | --- | --- | --- |
| Goal workspace | selected goal/map branches and concise retained state | fixed North Star, current context, hypotheses, durable notes | choose the research path |
| Evidence tools | literature queries, source IDs, inspected records | candidate records, fetched content, claim-linked evidence receipts | treat search metadata as read evidence |
| Personal observations | value, unit, time, protocol, instrument, uncertainty, provenance | immutable observations and same-protocol descriptive series | infer causality or future response |
| Installed external models | engine-native inputs created for the question | native output files and logs | choose the research path |

The approved target is in [goal.json](goal.json): the whole-body human capability
frontier at 110–120 kg, including skeletal development. The previous combat map
in [goal-structure.json](goal-structure.json) is historical reference, not the
current goal or an active set of success conditions. Map edges do not prove
causality or authorize an intervention.

## Evidence and model discipline

`fetch_literature` preserves the exact response and returns a `fetch_id`.
`save_evidence` can use that ID instead of resending the payload and source
metadata; add a title when the source response has none. Scholarly appraisals
may be concise free text or structured fields. Claims still require located
passages and source-bounded interpretation.

External engines now run directly. Keep useful stdout/stderr, inputs and outputs
with the experiment files, including failures. Historical failed DB records remain
available for diagnosis and cannot support a successful model-result claim.

Search is paginated and fault-isolated. Retained scholarly evidence contains
the inspected payload, claims actually used, short located passages,
applicability, limitations, and a content hash. A PubMed record may resolve to
available PMC full text through Europe PMC; failure falls back to the exact
record with the limitation preserved.

External models are used only when their documented scale and inputs can change
the decision. When a result raises a quantitative question, Codex chooses the
relevant established relation or creates the smallest question-specific
provisional model, then calculates directly or with temporary code. Equations,
inputs, units, coefficient sources, assumptions, outputs, sensitivity,
uncertainty, and unresolved links remain visible. A calculation is promoted to a
permanent tool only after repeated use demonstrates a need. Local code may not
invent biological coefficients or a personal longitudinal simulator. Reference
and population runs support conditional conclusions; personalization requires
adequate comparable personal data and an explicitly justified calibration
method.

Every executed experiment preserves the exact question, all actual inputs,
units, timing, seeds, versions, provenance, raw outputs, uncertainty, failures,
and unresolved variables. When the user asks to see everything, these records
are shown directly or through a linked artifact.

## Chat use

Ask naturally, including several topics in one message. Codex treats them as a
temporary portfolio, investigates each far enough that an easy topic cannot
substitute for another, then synthesizes mechanisms, conflicts, trade-offs, and
whole-goal implications. Personal observations improve calibration but are not
required to begin evidence review, physics-based analysis, reference modeling,
or sensitivity experiments.

During a substantial run Codex shows material intermediate results, quantities
derived from them, questions they genuinely raised, and changes to the leading
strategy. The user can challenge assumptions, add observations, or redirect the
emphasis while research is running. Codex continues safe research without
making the user supply the next scientific question.

Research does not activate training, medical action, drugs or supplements,
purchases, bookings, external mutations, or a changed goal. Those require
explicit user approval.

## Optional long-running operation

The [joint-research runner guide](docs/RUNNER.md) covers explicit launch, live
human steering, native parallel research, event inspection, pause/recovery and
resource limits. Normal chat does not require the runner. Nothing starts or
activates a real-world strategy merely by installing these changes.

## Validation

```powershell
uv run python -m unittest discover -s tests -v
```

Architecture and language are defined in [docs/BLUEPRINT.md](docs/BLUEPRINT.md),
[CONTEXT.md](CONTEXT.md), and [AGENTS.md](AGENTS.md). Version-control boundaries
are in [docs/ARTIFACT_POLICY.md](docs/ARTIFACT_POLICY.md).
