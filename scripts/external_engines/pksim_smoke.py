"""Run PK-Sim's official V12 test project and verify exported CSV artifacts.

This is an engine/interface smoke test.  It does not qualify the bundled test
project for personal PBPK prediction or intervention selection.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import tempfile
from pathlib import Path


def _sha256(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runtime", type=Path, required=True)
    parser.add_argument("--project", type=Path, required=True)
    args = parser.parse_args()
    runtime = args.runtime.resolve()
    project = args.project.resolve()
    if not runtime.is_file():
        raise FileNotFoundError(runtime)
    if not project.is_file():
        raise FileNotFoundError(project)

    with tempfile.TemporaryDirectory(prefix="pksim-smoke-") as temporary:
        output = Path(temporary)
        completed = subprocess.run(
            (
                str(runtime),
                "export",
                "--project", str(project),
                "--output", str(output),
                "--run",
                "--csv",
                "--logLevel", "Information",
            ),
            cwd=runtime.parent,
            text=True,
            capture_output=True,
            timeout=600,
            check=False,
        )
        csv_files = sorted(output.rglob("*.csv"))
        if completed.returncode != 0:
            raise RuntimeError(
                f"PK-Sim smoke failed ({completed.returncode}): {completed.stderr}"
            )
        if not csv_files or any(path.stat().st_size == 0 for path in csv_files):
            raise RuntimeError("PK-Sim smoke produced no non-empty CSV artifacts")
        aggregate = hashlib.sha256()
        for path in csv_files:
            relative = path.relative_to(output).as_posix()
            aggregate.update(relative.encode("utf-8"))
            aggregate.update(bytes.fromhex(_sha256(path)))
        print(json.dumps({
            "runtime_sha256": _sha256(runtime),
            "project_sha256": _sha256(project),
            "exit_code": completed.returncode,
            "csv_artifact_count": len(csv_files),
            "csv_aggregate_sha256": aggregate.hexdigest(),
        }, sort_keys=True))


if __name__ == "__main__":
    main()
