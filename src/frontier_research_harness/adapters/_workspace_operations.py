"""Internal workspace implementation, grouped by responsibility."""
from __future__ import annotations

import json
from typing import Any
from uuid import uuid4
from frontier_research_harness.research_contracts import ResearchEntry
from frontier_research_harness.model_relevance import candidate_targets, model_layer
from ._workspace_common import (
    PROJECT_ROOT,
    _utc_now,
)


class WorkspaceOperationMixin:
    def research_log(self, operation: str, payload: dict[str, Any]) -> dict[str, Any]:
        if operation == "append":
            entry = ResearchEntry.model_validate(payload)
            if entry.in_reply_to and not self.connection.execute(
                "SELECT 1 FROM frontier_science_research_entries WHERE entry_id=?", (entry.in_reply_to,)
            ).fetchone():
                raise ValueError("unknown in_reply_to entry")
            entry_id, created_at = str(uuid4()), _utc_now()
            self.connection.execute(
                "INSERT INTO frontier_science_research_entries(entry_id,created_at,record_json) VALUES(?,?,?)",
                (entry_id, created_at, json.dumps(entry.model_dump(mode="json"), ensure_ascii=False)),
            )
            self.connection.commit()
            return {"entry_id": entry_id, "created_at": created_at, "record": entry.model_dump(mode="json"),
                    "activation": False, "verification": "UNASSESSED_NOTE"}
        if operation != "list" or set(payload) - {"after_sequence", "limit"}:
            raise ValueError("list accepts after_sequence and limit")
        after, limit = payload.get("after_sequence", 0), payload.get("limit", 20)
        if type(after) is not int or after < 0 or type(limit) is not int or not 1 <= limit <= 100:
            raise ValueError("after_sequence >= 0 and limit between 1 and 100 required")
        rows = self.connection.execute(
            "SELECT * FROM frontier_science_research_entries WHERE sequence>? ORDER BY sequence LIMIT ?",
            (after, limit + 1),
        ).fetchall()
        entries = [{"sequence": r["sequence"], "entry_id": r["entry_id"], "created_at": r["created_at"],
                    "record": json.loads(r["record_json"])} for r in rows[:limit]]
        return {"entries": entries, "more_available": len(rows) > limit,
                "next_after_sequence": entries[-1]["sequence"] if entries else after,
                "note": "Joint research notes and drafts are not verified evidence, approval, or activated plans."}

    def inspect_environment(self) -> dict[str, Any]:
        """Local capability inspection is not a network or host-exposure test."""
        return {
            "workspace_root": str(PROJECT_ROOT),
            "database": str(self.database.resolve()),
            "knowledge": self.list_knowledge_sources(),
            "external_model_guide": str(PROJECT_ROOT / "docs/EXTERNAL_MODELS.md"),
            "network_status": "NOT_PROBED",
            "host_tool_exposure": "HOST_MUST_VERIFY",
            "local_entrypoint": "python -m frontier_research_harness.adapters.research_cli",
            "note": "Configured sources and the guide are not proof of successful requests or scientific applicability.",
        }


    def load_experiment(self, experiment_id: str) -> dict[str, Any]:
        row = self.connection.execute(
            "SELECT * FROM frontier_science_experiments WHERE experiment_id=?",
            (experiment_id,),
        ).fetchone()
        if row is None:
            raise ValueError(f"unknown experiment: {experiment_id}")
        return {
            "experiment_id": row["experiment_id"],
            "status": row["status"],
            "created_at": row["created_at"],
            "question": row["question"],
            "model_name": row["model_name"],
            "model_version": row["model_version"],
            "research_layer": (
                model_layer(row["model_name"]).value
                if model_layer(row["model_name"]) else None
            ),
            "candidate_target_ids": list(candidate_targets(row["model_name"])),
            "input_hash": row["input_hash"],
            "input": json.loads(row["input_json"]),
            "raw_output": json.loads(row["output_json"]),
            "interpretation": row["interpretation"],
            "provenance": json.loads(row["provenance_json"]),
        }




    def load_calculation(self, calculation_id: str) -> dict[str, Any]:
        row = self.connection.execute(
            "SELECT * FROM frontier_science_calculations WHERE calculation_id=?",
            (calculation_id,),
        ).fetchone()
        if row is None:
            raise ValueError(f"unknown calculation: {calculation_id}")
        return {
            "calculation_id": row["calculation_id"],
            "created_at": row["created_at"],
            "target_id": row["target_id"],
            "formula_id": row["formula_id"],
            "formula_version": row["formula_version"],
            "input_hash": row["input_hash"],
            "input": json.loads(row["input_json"]),
            "output": json.loads(row["output_json"]),
        }
