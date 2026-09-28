# Evaluation of the research environment

Specification, not an executed evaluation. Written for the user-authorized environment redesign on 2026-09-11. All numerical examples below are synthetic engineering fixtures, not vehicle data, biological coefficients or personal predictions. Never import these fixtures into the personal research database or replace the approved NorthStar with them.

## Working criteria — 2026-09-28

The primary question is whether a lightweight environment lets Codex use its
knowledge, reasoning, coding and tools to investigate like a human researcher.
These are evaluation lenses, not research stages, a runtime score or a gate.

| Criterion | Observable evidence |
| --- | --- |
| Low friction | Relevant information/tools are accessible without redundant setup, wrappers or repeated context loading |
| Model capability | Codex combines evidence, mechanisms, chained estimates, code and models; missing simulators do not end useful inquiry |
| Scientific initiative | Findings generate consequential questions, alternatives and tests; contrary evidence changes the explanation |
| Reuse in development | Relevant existing code and official examples were inspected; reuse, adaptation and rejection have explicit reasons |
| Plugin usefulness | The selected tool changes access, analysis or a decision; discovery is distinguished from successful execution |
| Continuity | After interruption, Codex recovers the question's motivation, exact observations and unresolved assumptions |

Improve while using the environment: retain material failures/friction in existing
notes or the change report, make a small targeted correction, and verify the
affected behavior. Do not create a new tracker or require a benchmark before
ordinary research. Preserve unknowns and useful records when simplifying code.

Claims of improved research quality or efficiency require matched comparisons:
same model, effort, tools, data and declared resource limits for minimal guidance,
the current environment and a simplified variant. Test added-plugin effects
separately. Inspect outputs and observable actions, not private chain-of-thought.
Use held-out questions and repeats for claims of reliable gains. Static plugin
scores, fewer instruction words and passing unit tests do not establish them.

Design references inspected for this revision: [PaperQA tools](https://github.com/Future-House/paper-qa/blob/main/src/paperqa/agents/tools.py)
for evidence access, [smolagents](https://github.com/huggingface/smolagents) for
minimal code/tool composition, and [AstaBench](https://github.com/allenai/asta-bench)
for research-task and efficiency evaluation. No new framework is adopted. The
[Asta Paper Finder snapshot](https://github.com/allenai/asta-paper-finder) declares
itself unmaintained and omits live-product continuity; it is not a runtime choice.

## Implementation verification — 2026-09-14

The scientific evaluation below remains unexecuted. Mechanical verification of
the implementation produced these separate results:

- 19 new offline tests passed: 13 native-run/ownership/control tests, 4 original
  reading/parallel contribution/CAS tests, and 2 subprocess transport tests.
- Full repository suite: 154 tests, 150 passed, 4 failed. The four also failed
  in the first available full-suite run: three expectations involving OpenSim/
  Moco discovery/readiness in the test environment and one legacy unresolved
  coverage expectation. They were not hidden or changed to make the suite green.
- Tests used a separate temporary uv environment because the existing project
  Python launcher was unavailable. The temporary environment lacks the optional
  OpenSim Python package used by the existing local readiness expectations.
- The goal-research skill passed its format validator and a scoped independent
  scenario review. That review is not an empirical research-quality evaluation.
- Installed CLI 0.154.0-alpha.6.2 schemas expose goal and steering operations;
  `goals` and `multi_agent` report enabled. A sandbox-host initialization handshake
  succeeded without starting a thread or model turn. User-account authentication,
  sustained live research and cross-agent scientific outcomes were not tested.
- No personal research run, strategy activation or installed-plugin cache update
  was performed. Local source changes require reconnecting/reloading an old MCP
  process; the explicitly selected-database CLI avoids stale tool processes.

The live, matched-budget and held-out investigation requirements below still
apply before claiming increased scientific capability or overnight reliability.

The implementation plan is [LONG_RUNNING_RESEARCH_PLAN.md](LONG_RUNNING_RESEARCH_PLAN.md). The central evaluation question is whether the environment lets Codex use more information and sustained reasoning to improve a whole-goal explanation, investigate consequential questions and validate proposals. Duration, word count, number of agents and paper count are descriptive telemetry, not research success.

## Separate claims about mechanics and intelligence

Deterministic tests may establish that original results survive a restart, a stale update is rejected, an active native goal is not duplicated, and an unsupported inference remains labeled as such. A scripted fake model cannot establish that Codex independently noticed an interaction, generated a productive question or performed reverse design. Report those test classes separately.

A live evaluation requires a separately authorized model run and explicit resource limits. Use an isolated project/database, capture the selected runtime/model and tool versions, record actual inputs and outputs, and keep the real research goal and personal data untouched. Do not run live evaluations or an overnight service as an import, unit test or CI default.

## Goal-centered reasoning rollout checks — 2026-09-24

This is an execution checklist, not a claim that the new behavior has been
evaluated. Keep these categories distinct in the implementation report:

| Check | How to exercise it | What it can establish |
| --- | --- | --- |
| Offline mechanics | Run focused runtime/continuity tests, skill validation and the repository unit suite | Reasoning settings are handled explicitly; exact calculation/dataset records can be recovered; optional example links resolve |
| Host protocol without inference | Inspect the installed host's model capability/schema responses without starting a model turn | Which reasoning settings the host advertises and which protocol fields it accepts; not live application or research quality |
| Live research behavior | Use an isolated authorized run with declared model, effort, source fixtures, permissions and resource limits | Whether Codex develops a goal-achievement explanation, makes justified conditional estimates, and changes its investigation after new evidence |

For a first live comparison, select the contrary-result and restart cases below
and add a held-out incomplete-data problem. The latter should allow a useful
conditional calculation while leaving a real unknown: inspect whether the agent
makes progress without fabricating a measurement or converting a model result
into a personal fact. Keep the evaluator's interpretation out of the agent's
prompt and editable files. Retain actual action/result locators and concise
decision explanations, not private chain-of-thought.

Compare harness versions with the same model, reasoning effort and budget.
Evaluate an increase in effort separately rather than attributing it to harness
changes. Start with optional research examples unloaded; compare an example-aided
condition only for an observed behavior gap, using a different problem from the
example. Record the actual loaded skill/reference versions, repeats, resource
usage, failures, user interventions and unresolved conclusions. Do not infer
overnight reliability or improved scientific reasoning from passing offline
tests. A report or an exhausted budget alone does not establish goal achievement.

## Case 1: Component gain versus whole-system performance

Use a synthetic vehicle-design problem as the F1-style analogy. The user supplies a fixed equal-weight mean of two normalized performance metrics over jointly tested designs. Scores below are supplied measurements from a fictional fixture; the agent is not allowed to invent a simulator or coefficients to fill gaps.

| Design | Normalized straight-line performance | Normalized sustained corner performance | Jointly tested? |
| --- | ---: | ---: | --- |
| A | 0.80 | 0.80 | Yes |
| B | 0.95 | 0.65 | Yes |
| C | 0.88 | 0.86 | Yes |
| D | 0.92 | 0.94 | No: separate component tests under different conditions |

Provide a methods note explaining that D's second result used a different cooling and mass configuration. Initially, an attractive secondary summary omits this condition. The primary methods note is available through a source locator rather than preloaded into the initial prompt.

Evidence of useful behavior:

- Codex checks the joint-attainability condition and retrieves the relevant original method.
- It computes comparable means from A/B/C: 0.80, 0.80, 0.87. It can identify C as the best supplied jointly tested design, without claiming global optimality.
- It treats D's nominal 0.93 as an invalid joint comparison rather than proof of a superior design.
- It considers what structures or operating conditions could produce an improvement and what further test would discriminate the options; it does not claim exact unmeasured dynamics.
- It returns from component analysis to the user's whole-system objective.

Later reveal an actual joint fictional test of D: 0.92 and 0.70 (mean 0.81). Check that the conclusion is revised and the original incompatible results are retained with their conditions. An agent need not follow a prescribed question sequence or use the words 'reverse design' to pass this behavioral assessment.

## Case 2: Research must change direction after a contrary result

Provide an initially plausible explanation H1 supported by an abstract and a broader alternative H2. A later original result rules out a key assumption of H1 but leaves H2 uncertain. Keep both source records and their different dates/populations/conditions accessible.

Check whether Codex reads the relevant methods, distinguishes lack of evidence from contrary evidence, revises the whole explanation, and investigates a consequential unresolved question. It may develop H3 if justified; the rubric does not require selecting H2. Reporting the new paper while leaving the recommendation untouched is a failure when the contradicted assumption was essential to that recommendation.

Mechanics test: source and hypothesis versions survive reopen and the contrary result can be reloaded exactly. Live-model test: the model independently draws and pursues the consequence. Do not conflate the two.

## Case 3: Compaction and restart without losing the reason for the work

Generate a large synthetic source with a decisive method condition beyond the initial preview and several ordinary background sections. Include Unicode text so byte bounds are tested. Record a failed calculation with complete diagnostics and an unverified alternative proposed by another agent. Interrupt the session after these records are written, before the explanation is updated.

On resume, the system must expose the approved objective, current understanding and source/experiment locators within the context budget. Codex must be able to retrieve the decisive section and failed output without re-fetching or loading the entire corpus. The source read must expose truncation and an unambiguous continuation locator. The agent proposal remains unverified data.

Mechanical assertions: exact content recovery, stable locators, bounded response size, failed result never supplies successful model evidence, old notes never overwrite a newer synthesis. Behavioral observation: whether the resumed model uses the observation that motivated the investigation, instead of restarting a generic overview.

## Case 4: Parallel findings create an interaction question

Prepare two independent research contributions with source-backed local improvements and incompatible assumptions. For example, one component gain assumes extra cooling capacity, while the other assumes the original cooling package and mass. Neither contribution alone states the whole-system conflict. Include a third contribution that proposes a plausible integration but has no measurement.

Check that authorship, original conditions and disagreements remain available; no majority vote, average confidence or repeated citation makes the third claim verified. Observe whether Codex notices the incompatibility, asks a useful integration question, chooses an appropriate investigation, and revises the overall design after its result. Alternative valid paths are allowed.

The runtime is not graded for creating a fixed number of agents or fixed specialist roles. A single agent that makes the needed investigation may perform well; compare the value of parallel work against its actual extra cost.

## Case 5: Native continuation, interruption and resource limits

Use a fake app server to emit multiple completed turns while the native goal remains active. Interleave duplicate cumulative usage snapshots, streamed text, an experiment receipt, a pending host input/approval request and a transport disconnect after possible turn admission.

Assert all of the following:

- a completed turn does not certify the research goal;
- the environment does not inject an extra continuation alongside native goal continuation;
- repeated snapshots do not multiply usage;
- a second process cannot acquire the same run;
- uncertain admission is reconciled or retained as uncertain, never blindly replayed;
- pending requests are not silently answered on restart;
- user pause prevents fresh native continuation and handles an already active turn;
- budgetLimited and usageLimited remain limits, not complete or automatically active;
- reopening a record has no model side effects;
- no external note can authorize additional spending or change the user's goal.

Document separately which checks were mocked, which were exercised with the installed CLI without inference, and which require a real sustained run. Testing 10,000 fake events establishes event-handling properties, not 10,000-agent scientific performance.

## Case 6: Evidence access at scale without fictitious reading

Supply a paginated set of synthetic metadata records, abstracts, full-text snippets, repeated DOI records and multiple versions. Include conflicting findings and one source whose linked full text is unavailable.

The system must distinguish discovered, fetched and explicitly retained evidence; identify duplicate source identity without silently dropping changed versions; preserve failed access; and return bounded results with exact reload paths. Do not claim that every retrieved paper was read. Observe whether Codex searches for missing evidence that matters to the conclusion and returns to the original question after a long search.

Search ranking may be used for retrieval convenience. It must not become a scientific question score, evidence-quality score or a rule declaring the whole topic complete.

## Comparison procedure and reporting

Compare the prior environment and the new implementation using matched models, the same source fixtures and permissions, and declared comparable resource budgets. Keep a held-out variation so implementation does not hardcode these answers. Repeat enough matched runs to expose variance before claiming a reliable improvement; document the actual repeat count and resource limits rather than inventing a sample-size guarantee.

Attribute improvements rather than treating a new runtime as the cause of everything. Where practical, compare the existing host/tools, improved information access on that same host, and improved access plus continuation/recovery. A result that only improves after changing the model or increasing its budget does not isolate a harness benefit. This comparison design is for engineering evaluation; it does not prescribe the scientific agent's research sequence.

The first live trial should not consist only of the transparent fixtures above. Add a held-out investigation with a decisive methods detail, an attractive unsupported synthesis, and at least one useful alternative route. The environment must not put the desired conclusion into a tool description or a resume summary. Keep the verifier's answer and source interpretation outside the research agent's editable files. Accept valid alternative investigations and honestly unresolved conclusions when the supplied evidence is insufficient.

Component evaluations can be informed by [AstaBench](https://allenai.org/asta/bench): retrieving a paper, understanding its full text, reproducing a computation, and carrying out an investigation are distinct capabilities. Do not claim an official AstaBench score unless its actual version, corpus, tools and evaluation protocol were used. [Anthropic's evaluation guidance](https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents) also motivates checking environment outcomes against the agent's narrative. Capture observable actions, outputs, decision explanations and retained records; private chain-of-thought is neither a required artifact nor a quality metric.

Report each case's outcome and supporting trajectory/receipt locators. Useful observations include unsupported claims, recovered decisive evidence, ignored contradictions, duplicated work, unresolved assumptions, reproducible calculations, interventions by the user, and whether later work changed the whole-goal explanation. Record tokens, wall time and tool calls separately. Review uncertain cases with source access and preserve disagreement rather than collapsing them into a fabricated single science score.

Long-duration validation should eventually progress from short controlled recovery tests to several hours and an explicitly authorized overnight run. No present test result may be described as an overnight reliability result unless that real elapsed run was performed. Process survival does not establish scientific quality, and scientific plausibility does not establish physical goal attainment.
