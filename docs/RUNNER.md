# Long-running joint research

Normal Codex chat uses the project instructions and research tools. You can ask
questions and change research emphasis while Codex investigates. Subagents use
native collaboration; no fixed team size or scientific workflow is imposed.

For a separately launched, long-running **foreground** native goal, the optional
runner records events, controls and recovery. This is not an installed background
service: the computer and process must remain running. It uses installed Codex
authentication, not a new API-key client. Launching consumes the host account's
usage; `prepare`, local `status` and `events` do not invoke a model.

## Explicit launch

From the project directory, with a working project Python environment:

```powershell
$runtimeDb = Join-Path $PWD 'data/personal/research-runtime.sqlite3'
function research-runner { uv run python -m frontier_research_harness.adapters.research_runner_cli --runtime-database $runtimeDb @args }
research-runner prepare --project $PWD --research-database 'ABSOLUTE_EXISTING_RESEARCH_DB' --token-budget 100000 --time-budget-seconds 14400
research-runner start RUN_ID_RETURNED_BY_PREPARE
```

The numbers are explicit example limits, not recommended scientific budgets.
Choose the actual research database deliberately; no default database is silently
selected. The approved goal file is hashed at prepare time and cannot silently
change on resume. At start, model selection uses the project host configuration
unless `--model` is supplied; the resolved model is pinned for subsequent resumes.
The runner records and uses the Python executable that prepared it.

New CLI preparations default to `--reasoning-effort highest_supported`. At start,
the runner reads the host model catalog (including pagination), selects the highest
recognized effort supported by that model, and sets it only on this research
thread. It does not change global configuration or switch models. Use an explicit
supported effort such as `--reasoning-effort high`, or `--reasoning-effort inherit`
to leave effort to the host. Legacy preparations and the Python API's omitted
effort retain inherited behavior.

The thread response must confirm requested model/effort before the runner creates
or activates its goal. Unknown effort rankings or unsupported requests stop before
thread creation. On resume the saved settings are reapplied; a mismatch parks the
goal and requires inspection. `status` includes requested, resolved and observed
settings in `execution`. Confirmation covers the host's start/resume response,
not an independent measurement of every later inference or child agent.

Source instruction hashes are recorded at start and resume for comparison. They
identify available local files, not proof that every optional reference was loaded.
The runner reads this checkout's research skill; updating source files does not
update a separately installed plugin cache. Research examples are optional fictional
references, not evidence or a required workflow.

`start` owns only the thread it creates. It binds the goal paused, then activates
native continuation without adding a competing `turn/start` loop. Intermediate
messages/tool events stream to stdout and persist in the runtime database.

## Human researcher controls

From another terminal with the same helper and runtime path:

```powershell
research-runner events RUN_ID --after 0 --limit 100
research-runner steer RUN_ID 'The control also looks abnormal. Investigate another mechanism.'
research-runner controls RUN_ID
research-runner status RUN_ID
research-runner pause RUN_ID
```

`steer` queues through idle gaps, records your contribution in the selected research
database, and sends it to the confirmed active turn. Check `controls` for PENDING,
DONE or FAILED: queuing is not delivery. A dispatch with an uncertain acknowledgement
is not resent automatically. If a question races a completed turn and is rejected,
its record remains; inspect the failed control before explicitly resubmitting it.

Your scientific objection does not authorize goal replacement, spending or physical
activation. Codex remains responsible for further questions, source investigation,
grounded calculations and synthesis while incorporating your direction.

`status` is a local snapshot, not a live account/host query. It also exposes pending
host requests. For an approval/input request, inspect its exact method and fields,
then supply a matching JSON response in a local file explicitly:

```powershell
research-runner respond RUN_ID REQUEST_ID --input response.json
```

No request is auto-approved. Responses are marked SENT, not independently verified
as accepted by the host. The foreground runner must be running to process controls.

## Stop, resume and recover

- `pause` / `stop` queue a pause of native continuation and interruption of the
  known active turn. Ctrl+C does the same in the foreground process.
- `resume RUN_ID` reconnects without changing a paused/limited/completed goal.
- `activate RUN_ID` explicitly continues a paused goal without resetting usage.
- `recover RUN_ID --prior-host-stopped` is only for an unclean exit, **after you
  confirm the previous owned host process has stopped**. It reconciles the saved
  goal and parks active work. It does not start research. Then inspect status and,
  if appropriate, activate explicitly.
- An uncertain thread creation with no acknowledged thread ID cannot be recovered
  automatically. Inspect host history rather than creating a duplicate thread.
- Time limits count from first activation, including downtime. Exhausted budgets
  require a new explicitly budgeted run, never an automatic reset.

Machine sleep or a dead controller cannot enforce a real-time deadline; enforcement
resumes when the process can run. Native token limits remain host responsibilities.
An OS lock prevents two controllers of the same run, not interference by an
unrelated application manually editing the same native thread.

## Evidence and parallel results

Use `search_retained` for literal discovery in a frozen append-only range and
`read_original_record` for byte-bounded originals/find-text. Continue with the
returned hash and offset. Agent contributions use `author: CODEX`, `agent_id` and
`session_id`; they never become human approval. Before replacing understanding,
pass `load_research.updated_at` as `save_research.expected_updated_at`. On conflict,
reload and reconcile both observations. The code does not choose the synthesis.

Recent activity and retained searches also locate numerical calculation receipts
(including failures) and registered dataset metadata. Reload their public records
before relying on a prior result. Dataset file contents are not automatically
loaded into the research context. Legacy databases without those optional tables
remain readable without creating the tables during these lookups.

## Verification boundaries

Offline tests exercise ownership, native-goal operations, steering, budgets,
transport EOF/stderr, UTF-8 original recovery, search pagination and write races.
Installed Codex 0.154.0-alpha.6.2 schemas were inspected and initialization was
tested without creating a thread. The thread-local effort fields and catalog
contract were additionally checked against generated schemas from installed Codex
0.155.0-alpha.16.3; offline tests cover effort mismatch and resume pinning.
Neither check establishes live model performance,
cross-agent scientific quality or an overnight run. Use the matched-budget,
held-out evaluations in [RESEARCH_ENVIRONMENT_EVAL.md](RESEARCH_ENVIRONMENT_EVAL.md)
before making those claims. No live research is automatically launched by tests.
