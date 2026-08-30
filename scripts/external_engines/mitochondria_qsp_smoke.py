"""Run a pinned minimal ODE integration of the Pfizer mitochondrial QSP model."""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--octave", type=Path, required=True)
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    args = parser.parse_args()
    driver = Path(__file__).with_suffix(".m").resolve()
    for path in (args.octave, args.model, driver):
        if not path.exists():
            raise FileNotFoundError(path)
    with tempfile.TemporaryDirectory(prefix="mitochondria-qsp-smoke-") as temporary:
        output = Path(temporary) / "result.json"
        completed = subprocess.run(
            (
                str(args.octave.resolve()), "--quiet", "--no-gui",
                str(driver), str(args.model.resolve()), str(output),
            ),
            text=True,
            capture_output=True,
            timeout=120,
            check=False,
        )
        if completed.returncode != 0 or not output.is_file():
            raise RuntimeError(
                f"mitochondrial QSP smoke failed ({completed.returncode}): {completed.stderr}"
            )
        result = json.loads(output.read_text(encoding="utf-8"))
    if result["state_count"] != 109 or not result["finite"]:
        raise RuntimeError(f"unexpected mitochondrial QSP result: {result}")
    payload = {
        "schema_version": "external-model-asset-receipt-v1",
        "component_id": "mitochondria_qsp",
        "engine": {
            "name": "GNU Octave",
            "version": "11.3.0",
            "runtime_path": str(args.octave.resolve()),
            "runtime_sha256": sha256(args.octave),
        },
        "model": {
            "name": "In Silico Mitochondria Muscle Metabolism QSP Model",
            "version": "git:e7513d3dca20673bfee0bfebaff41132009593e5",
            "source_path": str(args.model.resolve()),
            "cell_dynamics_sha256": sha256(args.model / "Cell_dxdT.m"),
        },
        "smoke": result,
        "stderr_note": completed.stderr.strip(),
        "scientific_boundary": (
            "A short finite ODE integration establishes Octave technical compatibility only; "
            "it does not reproduce the paper, validate physiology, or support personal prediction."
        ),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    args.receipt.parent.mkdir(parents=True, exist_ok=True)
    args.receipt.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
