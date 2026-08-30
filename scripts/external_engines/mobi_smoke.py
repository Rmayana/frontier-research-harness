"""Run an official MoBi PKML model through OSPSuite-R/SimModel.

MoBi's stable portable release has no CLI.  This verifies the official model
calculation interface separately from the MoBi GUI installation and does not
qualify any project for personal prediction.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
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
    parser.add_argument("--rscript", type=Path, required=True)
    parser.add_argument("--library", type=Path, required=True)
    parser.add_argument("--model", type=Path, required=True)
    args = parser.parse_args()
    driver = Path(__file__).with_suffix(".R")
    for path in (args.rscript, args.library, args.model, driver):
        if not path.exists():
            raise FileNotFoundError(path)
    with tempfile.TemporaryDirectory(prefix="mobi-smoke-") as temporary:
        staging = Path(temporary)
        staged_model = staging / "run.pkml"
        staged_driver = staging / "mobi_smoke.R"
        shutil.copy2(args.model, staged_model)
        shutil.copy2(driver, staged_driver)
        environment = os.environ.copy()
        environment["R_LIBS_USER"] = str(args.library.resolve())
        environment["LANG"] = "English_United States.1252"
        completed = subprocess.run(
            (str(args.rscript.resolve()), "--vanilla", str(staged_driver), str(staged_model)),
            cwd=staging,
            env=environment,
            text=True,
            capture_output=True,
            timeout=300,
            check=False,
        )
        if completed.returncode != 0:
            raise RuntimeError(f"MoBi smoke failed: {completed.stderr}")
        payload = json.loads(completed.stdout)
        if payload["value_count"] < 1:
            raise RuntimeError("MoBi smoke returned no values")
        payload.update({
            "exit_code": completed.returncode,
            "model_sha256": _sha256(args.model),
            "rscript_sha256": _sha256(args.rscript),
        })
        print(json.dumps(payload, sort_keys=True))


if __name__ == "__main__":
    main()
