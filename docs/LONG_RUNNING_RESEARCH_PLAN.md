# Long-running Codex-led research environment

Current implementation note (2026-09-14): the user subsequently authorized
implementation in the current workspace and participation as a human researcher.
The earlier separate-task sequencing below is historical, not an instruction to
create another task. Current operation and limits are documented in [RUNNER.md](RUNNER.md)
and [ADR 0005](adr/0005-native-research-operation.md). Offline implementation tests
do not establish live scientific quality or an overnight run.

Implementation brief researched by Astra on 2026-09-10/11, for a SEPARATE NEW Sol task after design research. The user explicitly corrected the sequence: Astra researches and designs here; Sol implements in a new chat, not as a subagent in this chat. This is an engineering plan, not a required scientific workflow. Building and offline validation in that new task are authorized; starting a persistent research service, spending API credits, changing credentials, or activating physical interventions is not part of this implementation run.

## Intended outcome and design philosophy

Give Codex the environment needed to sustain open-ended research across long sessions, many sources, computations, failures, and interruptions. Maximize the use of Codex's intelligence and information processing. Codex chooses and revises questions, explanations, hypotheses, methods, models, experiments, interpretation, synthesis, and strategy. Code supplies reliable access, execution, provenance, and recovery.

The user's F1 analogy means designing the whole system for its intended performance and constraints, deriving possible component requirements, testing whole-system consequences, and revisiting architecture when component findings change the picture. It does not mean adding an F1 simulator or prescribing a fixed top-down pipeline. Research must move backward, forward, across scales, and sideways across interacting systems. More papers, tokens, roles, questions, or elapsed time are not evidence of a better result by themselves.

Preserve goal.json, goal-structure.json, supplied target tables, personal records, and the current NorthStar: equal-weight arithmetic mean of normalized whole-body metrics over jointly attainable configurations at 110–120 kg, including skeletal development. Do not substitute weakest-link, Pareto-only, previous combat targets, a deadline, or a new objective. Do not claim that a model-bounded optimum establishes an absolute human maximum. A report, a completed model turn, a stopped process, and actual goal attainment are different things.

## Research questions that changed this plan

| Question | Evidence and implementation decision |
| --- | --- |
| Is lack of a scheduler the only failure? | No. Existing BLUEPRINT already requests ongoing causal research. Address usable evidence access, recoverable reasoning context, observable execution and evaluation as well as continuity. Do not claim code forces intelligent questions. |
| Should we build another scientist/controller? | No. Native Codex goal continuation exists in the installed protocol. Prefer it to a second loop injecting generic 'continue' prompts. No coded scientific completion authority, question ranking, fixed roles or research phases. |
| Does the Python SDK eliminate protocol work? | Its official public API handles sessions, turns, streams and steering, but the inspected reference does not expose goal set/get. Verify before selecting it. Prefer public SDK reuse if sufficient; otherwise a narrow, tested stdio app-server adapter for the required methods is justified. Do not depend on private SDK internals. |
| Can the runner operate on the user's active desktop conversation? | Default to runner-owned sessions only. An idle read followed by turn/start is not an atomic ownership guarantee. Never silently attach, interrupt or steer an unrelated human session. |
| Does turn/completed end research? | No. Track native goal and transport/run states separately. Continue consuming native continuation events; no turn-count success threshold. |
| Does a stored summary recover all knowledge? | No. Keep original records accessible by locator, plus revisable current understanding. Do not repeatedly load the entire corpus or rely on summary-only memory. |
| Do unit tests prove reverse-design intelligence? | No. Deterministic tests prove access, persistence, ordering and failure handling. A separate, opt-in live evaluation must assess whether the model notices interactions and changes its explanation. |
| Can retries guarantee exactly-once external actions? | No. Preserve dispatch intent and acknowledgement. Reconcile uncertain submissions with the host; never blindly replay a possibly admitted turn or non-idempotent external job. |
| Should the runner install a background service immediately? | No. Implement explicit foreground operation and recovery first. No automatic boot installation, global config change, plugin reinstall, live scientific run or new credentials. |
| Can we retain the existing research core? | Yes. It already stores fetches, evidence, experiment failures and understanding history. Extend seams rather than replace the scientific contracts or duplicate the corpus. |

## Investigated implementations and bounded reuse

1. [Codex App Server](https://learn.chatgpt.com/docs/app-server), [official source](https://github.com/openai/codex/tree/main/codex-rs/app-server), and [Python SDK](https://github.com/openai/codex/tree/main/sdk/python): session/turn lifecycle, streaming, goal state and sandbox boundary. Apache-2.0. Local CLI inspected: 0.153.4. Its experimental JSON schema was generated without a model call into `%TEMP%/frontier-codex-schema-20260910`; `ThreadGoalSetParams`, goal notifications, and native status enums are present. These are interface observations, not a live continuation test. Public SDK releases pin compatible runtime versions; validate the actual selected runtime, not GitHub main alone.
2. [Anthropic long-running harness](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents), [later harness revisions](https://www.anthropic.com/engineering/harness-design-long-running-apps), [Managed Agents](https://www.anthropic.com/engineering/managed-agents): recoverable session logs and separable execution environment; avoid freezing workarounds that stronger models no longer need. Do not copy mandatory planner/reviewer or sprint architecture.
3. [Context engineering](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents): original-source locators, selective retrieval, compact usable tool outputs. No mandatory all-context dump.
4. [LangGraph persistence](https://docs.langchain.com/oss/python/langgraph/persistence) and [Temporal workflows](https://docs.temporal.io/workflows): separate durable state from live context; record external execution outcomes and recover interruptions. No framework dependency is needed merely to imitate these ideas. Temporal is a later option only if multi-host orchestration creates a demonstrated need.
5. [AIDE](https://github.com/wecoai/aideml) (MIT), [AI Scientist v2](https://github.com/SakanaAI/AI-Scientist-v2), [ShinkaEvolve](https://github.com/SakanaAI/ShinkaEvolve): preserve alternative attempts, execution feedback and useful cross-branch results. Do not import a fixed research tree policy, stages, or single scalar biological fitness. Check exact license before any code adaptation; current plan requires no copied implementation from these projects.
6. [Kosmos paper](https://arxiv.org/html/2511.02824v1), [Robin](https://github.com/Future-House/robin), [Virtual Lab](https://github.com/zou-group/virtual-lab): share source-linked discoveries and use external scientific tools. A shared research 'world model' is not a physiological simulator; fluent synthesis is not validation.
7. [PaperQA](https://github.com/Future-House/paper-qa), [Asta Paper Finder](https://github.com/allenai/asta-paper-finder), [Jina DeepResearch](https://github.com/jina-ai/node-DeepResearch): evidence navigation and targeted re-reading. Reuse current scholarly adapters first; no paid search integration or corpus download is required for this implementation.
8. [AIRAS](https://github.com/airas-org/airas) and [autoresearch](https://github.com/karpathy/autoresearch): immutable measured results and evaluation independence. No mandatory preregistered paper, no agent-editable evaluation truth, no forced keep/discard policy for scientific explanations.
9. [Open Deep Research code](https://github.com/langchain-ai/open_deep_research/blob/main/src/open_deep_research/deep_researcher.py): study concrete early-exit paths; never translate iteration exhaustion or an exception into solved research. Repository was archived at the time inspected.
10. [OpenAI Navier–Stokes announcement](https://openai.com/index/navier-stokes-solution/) and [proof repository](https://github.com/openai/NavierStokesAndEuler): diverse approaches, transfer of intermediate results, and independently checkable target alignment. Public proof artifacts are not the internal discovery harness. Do not claim to reproduce that model, compute scale, or scientific outcome.
11. [NASA system design](https://www.nasa.gov/reference/4-0-system-design-processes/) and [logical decomposition](https://www.nasa.gov/reference/4-3-logical-decomposition/): derive design requirements from whole-system outcomes and revise them through recursive analysis of interacting components. Borrow this engineering reasoning, not NASA's project phases or approval gates.
12. [Codex issue 38289](https://github.com/openai/codex/issues/38289) and [42622](https://github.com/openai/codex/issues/42622): reported admission-race and request-durability limitations motivate tests and conservative recovery. Reports are not proof that the installed version exhibits every reported bug.

## Implementation scope

### Research capabilities determine the implementation

The execution adapter is supporting infrastructure, not the central scientific improvement. Derive the environment from what Codex must be able to investigate. The following are capabilities and engineering acceptance conditions, not a sequence of scientific phases.

| Required research behavior | Existing support and observed gap | Implementation consequence |
| --- | --- | --- |
| Find why apparently compatible component gains cannot coexist | Existing source navigation lists references, links and section titles; it does not read a selected section. Exact evidence loads return entire records. | Offer searchable stored originals plus bounded reads with surrounding context and stable continuation. Source methods and conditions must remain recoverable beyond the initial preview. |
| Move from a whole-system aim to mechanisms and back | Current understanding, goal map, notes and model catalog already exist. The goal map is passive and not a mandatory causal graph. | Preserve these. Improve access to original assumptions, failed results and comparison outputs; do not add a deterministic reverse-design engine. |
| Derive a new question from an unexpected result | The research log and free-text understanding can already retain questions and explanations. | Keep that freedom. Demonstrate with an evaluation where a new result changes the useful investigation, rather than implement a question generator or score. |
| Remember an alternative that was unpromising before a new observation | Historical understanding and exact receipts exist, but recent-context loading is not a search of all stored knowledge. | Provide bounded search across retained records and ordinary notes. Preserve disagreement and unsuccessful routes without forcing them into winner/loser branches. |
| Reproduce an important calculation | Qualified model receipts exist. A shell/notebook result and a model receipt have different contracts. | Reuse the existing host for Codex-written arithmetic and analysis. Retain script/input/output/version locators through existing research entries; never relabel arbitrary code as a validated biological model. |
| Continue after compaction without restarting a generic review | `load_research` already returns approved intent, understanding and recent receipt locators. | Test retrieval from the original that motivated unfinished work. Add optional revision checks on synthesis updates, not a second compulsory memory schema. |
| Use parallel results without losing incompatible assumptions | Native delegation and append-only contributions can support independent work. | Keep original authorship and source conditions; Codex integrates them. Shared summary updates must detect stale revisions through the public interface. |

Concrete local interface observations on 2026-09-11: `search_literature` already accepts a query portfolio and cursors; `research_log` already pages by sequence; `load_evidence` and `load_experiment` return full original records; `list_experiments` has a limit but no continuation cursor. The inspected MCP tool catalog exposes neither `load_literature_fetch` nor the draft `read_original_record`. Merely adding a workspace method therefore does not provide the capability to Codex. Wire any addition through the same Module Interface used by MCP and the JSON CLI, then test that route. Do not invent or document nonexistent tool names.

For source access, a small coherent surface is preferable to many near-duplicate tools. An exact/text search returning record identity, source title, content level, matching context and a reload locator, plus bounded reading of that locator, is sufficient initially. Read navigation should support finding a section or a term inside a selected original before paging from byte zero through a large JSON object. The precise public names remain an implementation choice; all documented examples must match the shipped schema.

Treat the requested content bound and the full response bound explicitly. Quotes, escapes, provenance and navigation can make a JSON envelope larger than its text payload. Test Unicode, boundaries inside multi-byte characters, beyond-end cursors, immutable version mismatches, and monotonic continuation. Reject an invalid cursor rather than return an empty page with the same cursor indefinitely. Keep raw serialized bytes and canonical semantic hashes distinguishable. Experiment originals span input/output/provenance columns; inspect their real schema rather than assume every table has a `record_json` column.

Do not require embedding calls or another model to read stored text. Begin with existing storage and exact/text search. If a later measured retrieval failure justifies semantic indexing, keep it replaceable, preserve exact originals and compare against the simpler route at equal resources. Scientific relevance and strength of evidence remain Codex judgments.

### Alternatives considered and why this boundary was selected

| Architecture | Benefit | Limitation and decision |
| --- | --- | --- |
| Existing Codex host plus improved research tools only | Smallest addition; native reasoning, tools, context handling and delegation remain intact. | Use this as the baseline and keep it usable independently. It does not by itself establish unattended process recovery or operator control. |
| Native Codex continuation plus a thin optional operation adapter | Adds explicit start/pause/recovery and observable execution while retaining the native agent loop. | Selected for the requested long-running capability, contingent on actual host support. It must not become a second scientific scheduler. |
| Full LangGraph/Temporal/research-agent framework | Useful execution abstractions, especially for distributed services. | Not selected for this single-host implementation: duplicated control, more integration and additional context/policy surface without a demonstrated need. |
| Prompt-only instructions to read more and think longer | Cheap and sometimes useful direction. | Necessary intent cannot substitute for original access, execution feedback or measured behavior. A minimum paper count or elapsed duration would be an activity target, not proof of research quality. |

Native goal APIs being present in a generated schema is weaker evidence than an actual sustained run. The implementation must contain a usable opt-in route and honest capability inspection. A failed capability check must not quietly fall back to a custom infinite model-call loop. Keep operational error handling separate from judgments that the research is complete.

### Further source checks that changed the design

- [Asta Paper Finder](https://github.com/allenai/asta-paper-finder) explicitly describes its public repository as an unmaintained reproduction snapshot. It omits the live product's long-term conversation capabilities. Apache-2.0 makes inspection possible but does not establish maintenance or fitness as our runtime dependency.
- [Asta Scientific Corpus tools](https://allenai.org/asta/resources/mcp) demonstrate graph navigation and paper/snippet access; [Asta resources](https://allenai.org/asta/resources) separate scientific tools from agents and evaluation. This supports adaptable information-access interfaces. This plan does not assume its production index is installed or authorized, and does not request credentials.
- [PaperQA source](https://github.com/Future-House/paper-qa/blob/main/src/paperqa/agents/tools.py) and [repository](https://github.com/Future-House/paper-qa) inform source-grounded evidence access. Importing its complete answer/re-ranking agent would introduce separate model use and an answer-centered policy. Reuse existing scholarly access first; no PaperQA dependency is needed for exact local retrieval.
- [Anthropic tool design](https://www.anthropic.com/engineering/writing-tools-for-agents) motivates testing whether Codex can actually find and use relevant information with a small tool surface. Tool count and descriptions alone do not establish better performance; review observable tool trajectories and outcomes, not private reasoning length.
- [AstaBench](https://allenai.org/asta/bench) separates literature retrieval, full-text understanding, code execution, data analysis and end-to-end discovery. [Agent evaluation guidance](https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents) distinguishes a transcript's claims from the resulting environment state. Our evaluation therefore needs both component checks and whole-investigation cases. Passing retrieval alone cannot stand in for a better scientific explanation.

### A. Native execution adapter and durable operation records

Add a small optional runtime module outside the passive scientific core. Keep it callable through a clear local CLI/module boundary; importing the MCP server must not start a process, session, model call or background loop.

Support inspect/prepare/start/resume/status/pause/steer/events operations, choosing exact names with the existing CLI conventions. Inspect/prepare/status/events must work without model calls; prepare creates only a local execution specification. Native start/resume that can generate model work must be explicit, not a side effect of loading research. Clearly document that resuming an active native goal may restart work.

The start specification binds the project directory, research database, approved goal ID and digest, selected runtime, optional explicit model, and explicitly supplied resource limits. Preserve configured model selection when no override is given; Sol is the implementation model, not a new permanent research-model default. Do not invent token budgets or disable approvals. Workspace-write/read-only sandbox choices must respect configured policy; do not set full-access or silently approve host requests.

Create a persistent runner-owned Codex session, provide the approved research intent plus the existing skill/module entrypoints, bind native goal state, and consume native events. Capability-check the installed runtime and report unsupported features. Native continuation is the sole continuation owner. Do not introduce a fallback model-calling loop when it is unavailable. Do not start a new session every time a turn finishes.

Bind the selected database to the session's scholarly/workspace tool route explicitly. The agent must not accidentally read or write DEFAULT_DATABASE when a test or alternate project database was selected. Provide the existing JSON Module Interface as a reliable route if MCP configuration cannot safely be installed per session. Do not mutate global configuration or installed plugin cache.

Persist operation intent before dispatch, acknowledgement after receipt, managed thread ID, active turn ID, native goal snapshot, runtime identity, last consumed events and interruption information. Exclude authentication secrets; retain full scientific outputs through existing receipt storage rather than copying them into every event. Keep authoritative lifecycle records distinct from transient streamed text deltas. Duplicate delivery must not double-count usage or append duplicate terminal events. Missing usage remains unknown, not zero. Reconcile snapshot totals rather than summing cumulative totals repeatedly.

Use a single-writer lease/ownership mechanism for a managed run. All state mutations must be transactional and must preserve other runs. After a crash, inspect saved ownership, host thread/goal/turn state and pending dispatch before deciding whether to reattach; an uncertain admitted turn must not be replayed. If reconciliation cannot establish safety, retain an explicit needs-attention state. This is a transport condition, not a scientific verdict.

User pause must disable further native continuation before interrupting an active turn, then reconcile the host state. Interrupt-first can admit another native continuation. Do not automatically resume user-paused, usage-limited, budget-limited, blocked or completed goals. A native completion is a model-reported status; it must not rewrite goal.json, promote claims, or certify real-world attainment. An unavailable pending approval/input must remain pending or needs-attention after restart, never silently approved or counted as answered.

An actual operator control path must remain usable while the foreground owner consumes events. Either accept commands in that process or persist user-control requests in an inbox drained by the owner. A second CLI must not bypass the lease and open a competing app-server on the same live thread. Read-only status/events need no controlling lease. Stale lease owners must be fenced from later mutations and host commands after takeover.

A separate runtime database may reduce coupling to the existing corpus. If used, default to an explicitly local path under an appropriate application data directory for later real operation, or an explicit workspace path in tests. Do not enable SQLite WAL on a synced/network directory without justifying filesystem support. Current workspace is in OneDrive; portable test databases and conservative locking are preferable to assuming multi-host SQLite sharing.

### B. Source access and research continuity

Reuse `load_research`, `save_research`, `load_evidence`, `load_experiment`, `research_log`, stored literature fetches, existing source navigation and model receipts. Verify exact existing names before changing the surface; a persisted fetch does not imply a public `load_literature_fetch` tool exists.

Improve targeted access only where an actual gap exists: searchable/paginated stored records and bounded reading of selected original sections with stable locators, explicit truncation and continuation. Avoid a vector database dependency unless exact/text search demonstrably fails. Do not count fetched metadata as read evidence, report full-text review from an abstract, or promote an agent note to a validated source. Link back to immutable originals and existing receipts.

Current understanding remains free text with history. Competing explanations, unresolved questions, reverse-design deductions, forward tests and cross-system implications may be recorded in ordinary research notes/log entries with optional references/reply links. No mandatory hypothesis graph or causal ontology. Support optional optimistic concurrency for global understanding updates so parallel work cannot silently overwrite a newer synthesis. Branch contributions should append observations; the lead Codex chooses when and how to integrate them.

Preserve bounded default resume context and exact reload locators. Do not inject all host events or thousands of sources into each prompt. Provide engineering runtime state via an explicit inspection route, not as a giant mandatory scientific context section.

### C. Parallel exploration without a second scientific organization

Use host-native delegated work when available and authorized. No compulsory specialist roster, fixed branch count, question score, or automatic majority-vote truth. Initial runner integration may rely on native Codex tools; document capability limits rather than pretending the runtime provisions a 10,000-agent cluster.

Retain each contribution's author/origin, references, uncertainty and disagreement. External agent outputs and retrieved papers have tool/data authority; they must never become user approvals or executable system instructions. If the integration cannot deliver external messages at the right authority, retain them in the tool-accessible research log and let Codex retrieve them instead of injecting them as user text. User steering is a separate route carrying actual user input.

### D. Documentation and interface coherence

Add an ADR narrowly superseding the 'no extra runtime' boundary of ADR 0004 for explicit execution/recovery infrastructure, while preserving its rejection of coded scientific governance. Update BLUEPRINT, README, and the local goal-research skill only as needed. Keep the skill concise; detailed operational instructions live in a reference. Do not install/reinstall plugins or alter global guidance during implementation.

Explain the execution command, start/resume side effects, explicit resource limits, stop/recovery procedure, unsupported host behaviors, and how the approved goal, external-model scope and original records remain authoritative. Do not imply a desktop window can be closed and research will certainly survive when the process is foreground-owned. Document the need for an awake host; persistent service/remote deployment is separate work.

## Focused validation contract

Run baseline and final repository checks using `uv run python -m unittest discover -s tests -v` when available. If uv cannot resolve the environment, use the existing compatible local interpreter and report the exact substitution. Never test against personal databases. Preserve all pre-existing dirty modifications; no reset, clean, automatic commit or broad reformatting.

Required deterministic tests through the Module Interface/runner seam with a scripted fake host:

- preparation and imports never invoke a live model or start work;
- wrong runtime capabilities fail explicitly;
- selected project/database and unchanged goal digest survive reopen;
- many native turns can stream through a run without an external continuation prompt or false goal completion;
- process disconnect, missing acknowledgement and restart preserve uncertainty without duplicate admission;
- user pause and native paused/blocked/usageLimited/budgetLimited states do not auto-reactivate;
- turn failure/completion is distinct from native goal status and real-world success;
- repeated usage snapshots and events are idempotent;
- pending host requests cannot be auto-approved or reconstructed as answered after restart;
- two owners cannot control the same run; stale scientific synthesis updates fail explicitly;
- a large stored source can be read in bounded sections with stable continuation and no implicit read/verified promotion;
- contrary findings, failed model receipts, alternative explanations and backward/forward/cross-system notes survive reload with exact originals.

Add an offline end-to-end scenario, clearly synthetic, that prepares a run, receives several turns, records an unexpected cross-system tradeoff, disconnects, resumes, rereads the original result, preserves two candidate explanations, and records a revised whole-goal understanding. This tests environment mechanics, not whether an LLM independently reasoned correctly. Concrete scenarios and numerical fixtures are specified in [RESEARCH_ENVIRONMENT_EVAL.md](RESEARCH_ENVIRONMENT_EVAL.md).

Provide an opt-in live evaluation specification (not executed now) comparing the existing environment with the new one at the same model and controlled budget. Scenarios should include F1-like component/whole-system tradeoffs, a wrong but appealing explanation, contradictory evidence, an unsupported model extrapolation, context interruption and transfer of a useful partial result. Assess source-grounded revision and actual whole-goal return, not the presence of words like 'reverse design', a fixed number of questions, hidden chain-of-thought length, or a fabricated science-quality score. Report long-duration reliability only after a real measured run; accelerated fake time does not prove an overnight deployment.

## Delivery

Implement the coherent in-scope environment, focused tests and documentation. Challenge any detail of this plan that proves incompatible with the verified host API; explain and make the smallest evidence-backed adjustment. Do not silently drop runtime integration and deliver only prose, or invent unsupported API methods to meet the plan. Report exact changes, tests, known limitations, and which long-running/live scientific checks remain unexecuted. Research activation remains separate from building the environment.

The engineering dependency order is: establish the source baseline and public tool gaps; make evidence/recovery capabilities usable and independently testable; integrate the native operation adapter; run cross-component failure scenarios; document the optional live comparison. This orders software dependencies, not Codex's scientific thought. Sol may reorder independent implementation work.

The earlier `sol_build` subagent was interrupted after the user corrected the delegation mode. Three untracked drafts (`research_runtime.py`, `codex_app_server.py`, `adapters/research_runner_cli.py`) and partial workspace edits are present. They are unverified work in progress, not an approved architecture or a passing implementation. Do not continue them on trust. Review against this revised plan, reuse only sound pieces, and preserve the many unrelated existing changes. The earlier reported 135-test baseline predates completion of these drafts and cannot validate them.

Deliver implementation from the separate Sol task. The original Astra task remains the design/research discussion. Give the user a concise inline account of what changed and what was actually tested; do not make a file the only explanation. Do not claim that offline unit tests establish an overnight research run or frontier scientific performance.
