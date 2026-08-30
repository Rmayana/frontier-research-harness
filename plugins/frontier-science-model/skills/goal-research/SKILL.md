---
name: goal-research
description: Use Frontier Science Model for open-ended scientific research toward a user-defined personal goal, using current evidence and external models while Codex chooses the research path.
---

# Goal Research

Codex is the researcher and natural-language interface. Understand the user's
goal, current state, corrections, and preferences in ordinary language. Keep
database fields, internal identifiers, model plumbing, and legacy terminology
out of the conversation unless the user asks for them.

Load only the smallest useful workspace context. Treat effectiveness and
efficiency as continuing optimization objectives: seek a better route whenever
current evidence or model results justify one. Hypotheses should arise, change,
combine, or disappear naturally during research. Do not impose a separate
frontier-discovery phase, a fixed hypothesis count, a mandatory measurement
contract, a predeclared protocol, a gate, or a prebuilt 24-month plan.

When the user asks for several research topics in one chat message, treat them
as one research portfolio. Identify the topics yourself, investigate each far
enough that one topic does not substitute for another, then synthesize shared
mechanisms, conflicts, trade-offs, and the best combined implications for the
goal. Do not ask the user to create projects, fill forms, name internal fields,
or open separate threads. Use a separate task or recurring automation only when
the user explicitly requests it.

For substantial physical or physiological research, use current primary
evidence and relevant connected external scientific models rather than ending
with literature alone. Footage-only research on the boxing technical goal does
not require or benefit from an unrelated physiological simulation.
Use `search_literature` with the canonical shape
`{"queries":[{"source":"pubmed","query":"..."}],"page_size":25}`. For broad
questions, search independent query families across complementary sources and
follow returned `next_queries`; do not mistake the first page for a literature
review. Continue while additional pages or query reformulations are still
adding decision-relevant records, and stop when marginal useful coverage has
clearly plateaued rather than at an arbitrary paper count.

Search results are candidate metadata, not read evidence. Fetch and inspect the
decision-relevant primary records. `save_evidence` rejects metadata-only
scholarly records: retain the exact fetched/source payload, title, content
level, specific claims used, applicability, and limitations. Do not fetch the
same source identifier twice in one turn. For the boxing technical goal,
inspect primary fight footage and retain timestamped observations as
`EXTERNAL_PRIMARY_SOURCE` through `save_footage_observation`; literature about
generic boxing cannot substitute for the named athlete's actual decision
system. Use `list_footage_observations` and `compare_footage_observations` to
reload exact clips and labels, but let Codex judge semantic similarity and
opponent-specific variation.

For substantial research that includes physical targets, call `list_models`
with the exact physical target IDs in scope. Use its required model layers and
relevant models as routing evidence, not as a substitute for scientific
judgment. Successfully run and interpret a target-compatible experiment in
every returned layer during the current research turn. Listing, describing, or
reusing a prior run does not count. Within a layer, choose the model and
question that can most change the goal-level decision. If personal inputs are
unavailable, use a documented reference, boundary, or sensitivity input and
keep the resulting limitation explicit; never fabricate personal input.

Do not let the easiest executable model define the research agenda. For a broad
goal, move top-down through whole-person physiology, organ circulation,
musculoskeletal mechanics, tissue durability, and cellular metabolism wherever
the catalog marks that layer relevant. Before deepening an already-run layer,
resolve the other relevant layers. A model result may revise hypotheses inside
its context, but it cannot by itself replace explanations or unknowns at other
layers. Current `list_models` and `describe_model` status overrides an older
operational note about a runtime failure; retain a correction when the old
failure affected prior research.

For a request limited to Beterbiev technique, inspect extensive fight and
training footage, retain timestamped observations, and do not run a model
merely to satisfy the receipt.

Use `calculate_target`, or fault-isolated `calculate_targets` for a portfolio,
for unit-checked arithmetic and measurement-derived values for the 27 physical
targets. Use `assess_targets` to distinguish observed gaps from missing
measurements. Treat `EXACT` and `DATA_DERIVED` literally: neither is a forecast
of 24-month biological adaptation. Reuse the returned immutable calculation ID
when the number informs retained research.

At synthesis, pass a non-persistent `coverage` receipt to `save_research`.
Use `scope: whole_goal` when the user asks for the overall goal, strategy, or
feasibility; map every physical target ID plus `technical_goal` to retained
evidence and a concise `researched` or `unresolved` finding. Use
`selected_targets` only when the user explicitly asks about a narrower subset,
and list that exact subset in `requested_target_ids`. Do not compress a broad
goal into a few themes. The validator checks real evidence and experiment IDs;
attach each current-turn experiment only to a compatible target and cover every
required model layer. It does not store a plan, phase, gate, or coverage
inventory.

Include a short execution receipt in the answer: candidate records reviewed,
primary records fetched, evidence retained, external models actually run, goal
targets covered or unresolved, and persistence status. Do not describe research
as complete when a required tool call or completion check failed.

Start with the whole-person question, then move toward organ, tissue, cellular,
or molecular detail only where it can change the answer. Prefer established
external models used in their documented context over repository-built
whole-body simulators. Preserve exact inputs, versions, provenance, and raw
outputs. A successful model run is evidence inside that model's context, not
proof of a personal outcome.

Preserve the stored North Star and success conditions exactly. Do not soften
"same implementation" into loose inspiration, adaptation, or principle-level
similarity unless the user explicitly changes the goal.

Compare meaningful alternatives when comparison helps answer the question,
but do not create formal artifacts merely to satisfy a workflow. Save only
useful current state, retained evidence, experiment records, concise findings,
live hypotheses, promising methods, failures worth avoiding, and important
unknowns. Let Codex decide the next research action from the goal and evidence.

The plugin is a passive workspace, literature connection, and external-model
toolbox. It has no Planner, Reviewer, research state machine, strategy engine,
or authority to activate a real-world intervention.

Require explicit user approval before activating a strategy, changing the
fixed goal, taking medical action, using drugs or supplements, spending money,
booking an external action, or mutating external data. Do not schedule recurring
work unless the user explicitly asks for it.
