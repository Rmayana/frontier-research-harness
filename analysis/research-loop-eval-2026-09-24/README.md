# Research loop rollout — 2026-09-24

## Scope and baseline

The old installed skill and references are preserved in `baseline-installed/skills/`.
They came from the user's installed plugin version `0.3.0+codex.20260907102832`.
The old SKILL.md SHA-256 is
`B2CD8182D51FC705A069A4A7E467C22FAF19CEF2C555132E2D4F635DB62D7C8D`.
This is an instruction baseline, not a snapshot of the old Python runtime or
complete old harness. Do not describe the proposed comparison as a full historical
harness comparison.

The candidate retains scientific autonomy and existing boundaries. Repeated
human-collaboration, reporting and persistence sentences were merged. No new
scientific phases, mandatory experiment counts, scoring or approval gates were added.

## Proposed live pilot — not launched

Use the same currently configured model for both conditions; resolve and record
its exact identity before launch. Use explicit `high` effort if supported by that
model; otherwise agree on a supported common effort. Never silently substitute
a model. Disable highest-supported selection for this comparison.

Proposed ceiling: six runs, at most 10,000 host-accounted tokens and 10 minutes
per run, for at most 60,000 tokens and 60 minutes in total. This is a small pilot,
not a statistically reliable improvement estimate or a monetary quote. These
limits are proposed and need user approval before model execution.

Each of three cases has one baseline and one candidate run:

1. Contrary result: reveal a methods result that invalidates a strategy's key
   assumption. Observe the subsequent investigation, not just revised wording.
2. Restart: interrupt after a decisive receipt is saved but before synthesis;
   resume the same run without resetting its aggregate budget.
3. Incomplete data: a held-out synthetic engineering task with enough information
   for a useful conditional bound but insufficient information for a point forecast.

Keep tools, source fixtures, permissions and initial task wording identical within
each pair. Vary only the skill and its references. Use an isolated project and
database per run with synthetic goals; do not import personal records or change
the real goal. Keep fixture answers and this evaluator document outside the
agent-visible project. Avoid inherited project instructions that reveal the
candidate behavior to the baseline. Do not load optional examples initially.

Before launching, finalize held-out fixtures and a reviewer-only expected-results
sheet, freeze both instruction trees with hashes, and verify effective loaded
instructions and model/effort. Capture exact action/result locators, host usage,
elapsed time, interruptions and failures. If isolation or settings cannot be
confirmed, do not interpret the run as a valid paired comparison.

Report each case independently: supported strategy revision, recovery of the
decisive original, useful conditional progress, fabricated assumptions, repeated
work and unresolved claims. An honest unresolved result can be valid. Do not
reduce research quality to a fabricated single score or infer overnight reliability.

## Deployment boundary

Candidate plugin: `0.3.0+codex.20260924120219`. Reinstall through the configured
local marketplace; do not overwrite the cache manually. Verify the user's actual
installed tree against the source, not the sandbox account's plugin cache.
A new task is needed to exercise newly loaded skills/tools; an existing MCP
process may retain pre-edit Python code. Installation and offline tests do not
prove live research behavior.

## Executed verification

- `uv run python -m unittest discover -s tests -v`: 235 tests passed in 50.244 s.
- Official skill and plugin validators passed using temporary `uv --with pyyaml`;
  project dependencies were not changed. Initial validators lacked PyYAML.
- CLI reinstall confirmed the new version under `C:/Users/shdja/.codex/plugins/cache/`.
  The first sandbox invocation installed only under `CodexSandboxOffline`; the
  subsequent user-account invocation is the deployment result reported here.
- All six source plugin files matched the user-installed cache by SHA-256;
  the removed `hooks/hooks.json` was absent in the new cache.
- No live-model evaluation, real research run, personal-data mutation or strategy
  activation was performed. Existing unrelated working-tree changes were preserved.
