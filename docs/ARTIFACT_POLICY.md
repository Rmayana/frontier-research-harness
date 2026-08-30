# Artifact and version-control policy

The repository records contracts, source, tests, pinned model inputs, and small
verification receipts. It does not commit mutable personal research databases,
runtime installations, caches, or generated engine logs/results.

## Versioned

- source, tests, goal and architecture documents;
- portable input/model receipts and regeneration scripts;
- pinned model inputs and vendor sources needed for reproducibility; and
- scripts that regenerate external-engine results.

## Generated or local-only

- `.venv/`, `.scratch/`, `.uv-cache/`, build and coverage outputs;
- `data/personal/*.sqlite3*` because the database is mutable and may contain
  sensitive observations;
- personal JSON snapshots, machine-specific runtime manifests, and local
  install/smoke receipts that contain runtime paths;
- engine logs and `*Results.csv` files; and
- credentials, account sessions, licensed installers, and remote-compute
  secrets.

Every retained experiment stores exact input, version, provenance, raw output,
and hashes through the workspace. Large remote outputs belong in external
artifact storage; only their immutable receipt should enter retained research.

External source checkouts under `vendor/` are pinned Git submodules when they
have an upstream repository. Local untracked files inside those checkouts are
not removed or included by the harness baseline.

Before establishing a repository baseline, inspect `git status --short`, verify
that no credentials or unintended personal data are staged, run the full test
command, and only then create the first commit. Creating that commit remains an
explicit repository action rather than an automatic validation step.
