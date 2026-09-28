# ADR 0007: External models, a short guide, and on-demand experiment files

Status: Accepted by the user on 2026-09-26. Supersedes ADR 0006.

The user clarified that even a shared instrument interface and experiment-file
management layer are unnecessary. Codex creates each experiment's files when
needed and uses existing model APIs or executables directly.

Remove the model catalog/execution MCP wrapper, numerical workbench, dataset
registration/fitting service, population sampling service and dedicated simulator
archive API. Preserve engine installations and necessary native/file-format
adapters, raw reference data and all prior research/experiment files. Existing
research original-record reads can retrieve historical JSON without its old runtime.

The short external-model guide locates runtimes and their inputs/outputs. No new
framework, dependency, solver or mandatory experiment template replaces the removed
ones. Research notes, evidence access, observations and the approved goal are outside
this simulator simplification. Useful experiment code and results are ordinary files.
