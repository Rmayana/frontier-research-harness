# ADR 0005: Native continuation with a thin operation adapter

Status: Accepted for the user-authorized research-agent implementation.

## Decision

Retain ADR 0004's scientific authority boundary. Its exclusion of a scientific
state machine does not prohibit a transport lifecycle. The optional local runner
records a single native Codex goal; only Codex/native goal continuation selects
and continues research. No Planner, Reviewer, fixed roster, question ranking or
extra continuation prompt scheduler is introduced.

Reuse the installed Codex app-server protocol rather than adding another agent
framework. Official open-source [goal runtime](https://github.com/openai/codex/blob/main/codex-rs/ext/goal/src/runtime.rs)
and [client protocol](https://learn.chatgpt.com/docs/app-server) provide the needed
continuation and steering primitives. The existing small stdio adapter remains
appropriate for its narrow interface; no upstream source is copied. This work
does not claim to recreate OpenAI's private scientific model or research scale.

The human researcher can inspect events, ask questions and redirect emphasis.
Material steering is recorded separately from conclusions and physical action
approval. Native subagents do independent scientific work, exchange intermediate
findings and receive follow-ups; code neither defines their scientific roles nor
chooses which approach deserves resources.

## Operational boundaries

- Start only on explicit launch with a token and/or elapsed-time budget.
- Preserve native token accounting and a persisted elapsed deadline across resume.
  Elapsed-time limits conservatively include paused/offline time.
- One OS lock owns each run. Release after closing its owned subprocess. An
  unclean exit requires explicit prior-host-stop confirmation and reconciliation.
- Never replay uncertain thread creation, activation or steering. A missing
  acknowledged thread ID requires host-history inspection, not another start.
- Resume reconnects; activate explicitly restarts a paused goal. Limits and
  completion are not automatically reactivated. Recovery parks work, not starts it.
- Host requests require an explicit operator response. Recording SENT does not
  prove the host accepted or completed the requested action.
- Store exact events and operations. Usage is a host-reported snapshot, not a sum
  of repeated notifications; child events cannot overwrite root goal/turn state.
- Installed app-server schemas and a no-inference handshake are compatibility
  checks, not proof of authenticated research or overnight reliability.

## Information continuity

Expose original reading, literal retained search and optimistic synthesis writes
through both MCP and the existing JSON CLI. Search previews do not become read
evidence. Native collaboration uses attributed append-only entries and source
locators, not a second replicated research state machine.

The optional runner uses its explicitly selected database via the local CLI,
avoiding ambient/stale MCP servers configured for another database. Normal chat
can continue to use the existing MCP surface. No installed plugin cache, account
credentials, goal or personal research records are changed by deployment tests.
