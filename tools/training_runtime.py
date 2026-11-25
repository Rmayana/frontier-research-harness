"""Locate this user's host configuration without depending on the working directory."""

import json
import os
from pathlib import Path


def settings() -> dict[str, str]:
    override = os.getenv("FRONTIER_TRAINING_CONFIG")
    if override:
        paths = [Path(override)]
    else:
        paths = [Path(os.environ[key]) / suffix / "FrontierTraining" / "local-tools.json"
                 for key, suffix in (("LOCALAPPDATA", ""), ("USERPROFILE", "AppData/Local"))
                 if key in os.environ]
    for path in paths:
        if path.is_file():
            return json.loads(path.read_text(encoding="utf-8-sig"))
    raise FileNotFoundError("FrontierTraining/local-tools.json not found. See docs/TOOLS.md.")
