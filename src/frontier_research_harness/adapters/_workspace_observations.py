"""Internal workspace implementation, grouped by responsibility."""
from __future__ import annotations

import json
from typing import Any
from uuid import uuid4
from frontier_research_harness.personal_observations import PersonalObservation
from ._workspace_common import (
    _utc_now,
    _validate_tool_input,
)


class WorkspaceObservationMixin:

    def save_personal_observations(
        self, observations: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """Preserve personal measurements without interpreting cause or efficacy."""
        if not isinstance(observations, list) or not observations:
            raise ValueError("observations must be a non-empty array")
        if len(observations) > 100:
            raise ValueError("at most 100 observations may be saved at once")
        known_targets = self._known_research_target_ids()
        results: list[dict[str, Any]] = []
        for index, item in enumerate(observations):
            try:
                if not isinstance(item, dict):
                    raise ValueError("observation must be an object")
                validated = _validate_tool_input(PersonalObservation, item)
                unknown = sorted(set(validated.target_ids) - known_targets)
                if unknown:
                    raise ValueError(
                        "unknown target IDs: " + ", ".join(unknown)
                    )
                record = validated.model_dump(mode="json")
                record_hash = validated.record_hash()
                existing = self.connection.execute(
                    "SELECT observation_id,created_at FROM frontier_science_personal_observations WHERE record_hash=?",
                    (record_hash,),
                ).fetchone()
                if existing is not None:
                    results.append({
                        "index": index,
                        "status": "DEDUPLICATED",
                        "observation_id": existing["observation_id"],
                        "created_at": existing["created_at"],
                    })
                    continue
                observation_id = str(uuid4())
                created_at = _utc_now()
                self.connection.execute(
                    """
                    INSERT INTO frontier_science_personal_observations(
                      observation_id,created_at,observed_at,protocol_hash,record_hash,record_json
                    ) VALUES(?,?,?,?,?,?)
                    """,
                    (
                        observation_id,
                        created_at,
                        record["observed_at"],
                        validated.protocol_hash(),
                        record_hash,
                        json.dumps(record, ensure_ascii=False),
                    ),
                )
                results.append({
                    "index": index,
                    "status": "SAVED",
                    "observation_id": observation_id,
                    "created_at": created_at,
                    "protocol_hash": validated.protocol_hash(),
                })
            except (TypeError, ValueError) as exc:
                results.append({
                    "index": index,
                    "status": "INVALID",
                    "error": str(exc),
                })
        self.connection.commit()
        counts = {
            status: sum(item["status"] == status for item in results)
            for status in ("SAVED", "DEDUPLICATED", "INVALID")
        }
        return {
            "results": results,
            "counts": counts,
            "observation_count": len(observations),
            "interpretation_boundary": (
                "Immutable observations only; repeated values permit descriptive comparison, "
                "not causal attribution or personal efficacy prediction."
            ),
        }

    def list_personal_observations(
        self,
        *,
        target_ids: list[str] | None = None,
        limit: int = 50,
    ) -> dict[str, Any]:
        if limit < 1 or limit > 500:
            raise ValueError("personal observation limit must be between 1 and 500")
        selected: set[str] | None = None
        if target_ids is not None:
            if not isinstance(target_ids, list) or not target_ids:
                raise ValueError("target_ids must be a non-empty array")
            selected = {str(item).strip() for item in target_ids}
            known = self._known_goal_target_ids() | self._known_benchmark_ids()
            unknown = sorted(selected - known)
            if unknown:
                raise ValueError("unknown target IDs: " + ", ".join(unknown))
        rows = self.connection.execute(
            """
            SELECT observation_id,created_at,observed_at,protocol_hash,record_hash,record_json
            FROM frontier_science_personal_observations ORDER BY observed_at DESC
            """
        ).fetchall()
        matched = []
        for row in rows:
            record = json.loads(row["record_json"])
            if selected is not None and not selected.intersection(record["target_ids"]):
                continue
            matched.append({
                "observation_id": row["observation_id"],
                "created_at": row["created_at"],
                "protocol_hash": row["protocol_hash"],
                "record_hash": row["record_hash"],
                **record,
            })
        series: dict[str, list[dict[str, Any]]] = {}
        for item in reversed(matched):
            series.setdefault(item["protocol_hash"], []).append(item)
        summaries = []
        for protocol_hash, items in series.items():
            first, latest = items[0], items[-1]
            summaries.append({
                "protocol_hash": protocol_hash,
                "target_ids": first["target_ids"],
                "metric": first["metric"],
                "unit": first["unit"],
                "protocol": first["protocol"],
                "instrument": first.get("instrument"),
                "observation_count": len(items),
                "first_observed_at": first["observed_at"],
                "latest_observed_at": latest["observed_at"],
                "first_value": first["value"],
                "latest_value": latest["value"],
                "descriptive_delta": latest["value"] - first["value"],
            })
        summaries.sort(key=lambda item: item["latest_observed_at"], reverse=True)
        return {
            "observations": matched[:limit],
            "returned_count": min(len(matched), limit),
            "matched_count": len(matched),
            "series": summaries[:limit],
            "matched_series_count": len(summaries),
            "repeated_comparable_series_count": sum(
                item["observation_count"] >= 2 for item in summaries
            ),
            "interpretation_boundary": (
                "Series share target, metric, unit, protocol, and instrument. Deltas are "
                "descriptive only and do not identify an intervention effect."
            ),
        }
