"""Internal workspace implementation, grouped by responsibility."""
from __future__ import annotations

import json
from typing import Any
from uuid import uuid4
from frontier_research_harness.adapters.scientific_knowledge import ScientificKnowledgeClient
from frontier_research_harness.scientific_contracts import canonical_sha256
from frontier_research_harness.footage_contracts import FootageObservation
from frontier_research_harness.evidence_navigation import literature_navigation
from ._workspace_common import (
    EVIDENCE_CLASSIFICATIONS,
    EVIDENCE_CONTENT_LEVELS,
    TECHNICAL_GOAL_TARGET_ID,
    _jsonable,
    _literature_identity,
    _utc_now,
    _validate_tool_input,
)


class WorkspaceEvidenceMixin:
    def search_literature(
        self,
        source: str,
        query: str,
        limit: int = 10,
        *,
        cursor: str | None = None,
    ) -> dict[str, Any]:
        return ScientificKnowledgeClient().search(source, query, limit, cursor=cursor)

    def search_literature_portfolio(
        self,
        searches: list[dict[str, Any]],
        *,
        limit_per_search: int = 10,
    ) -> dict[str, Any]:
        if not 1 <= len(searches) <= 40:
            raise ValueError("queries must contain between 1 and 40 searches")
        client = ScientificKnowledgeClient()
        responses = []
        combined: list[dict[str, Any]] = []
        seen: set[str] = set()
        next_queries: list[dict[str, Any]] = []
        failed_searches = 0
        for index, search in enumerate(searches):
            source = search.get("source")
            query = search.get("query")
            if not isinstance(source, str) or not isinstance(query, str):
                raise ValueError("each portfolio search requires source and query strings")
            cursor = search.get("cursor")
            if cursor is not None and not isinstance(cursor, str):
                raise ValueError("query cursor must be a string")
            try:
                response = client.search(source, query, limit_per_search, cursor=cursor)
            except Exception as exc:
                failed_searches += 1
                responses.append({
                    "ok": False,
                    "source": source,
                    "query": query,
                    "cursor": cursor,
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                })
                continue
            response = {"ok": True, **response}
            responses.append(response)
            if response.get("next_cursor"):
                next_queries.append({
                    "source": source,
                    "query": query,
                    "cursor": response["next_cursor"],
                })
            for item in response.get("results", []):
                identity = _literature_identity(source, item)
                if identity in seen:
                    continue
                seen.add(identity)
                combined.append({"search_index": index, "source": source, **item})
        return {
            "searches": responses,
            "combined_results": combined,
            "attempted_search_count": len(searches),
            "completed_search_count": len(searches) - failed_searches,
            "failed_search_count": failed_searches,
            "returned_candidate_count": sum(
                int(response.get("returned_count", len(response.get("results", []))))
                for response in responses
                if response.get("ok")
            ),
            "unique_result_count": len(combined),
            "next_queries": next_queries,
            "more_available": bool(next_queries),
            "selection_owner": "Codex",
            "note": "Search discovers candidates. Follow next_queries for more pages, then fetch and read decision-relevant primary records before synthesis.",
        }

    def fetch_literature(self, source: str, identifier: str) -> dict[str, Any]:
        record = ScientificKnowledgeClient().fetch(source, identifier)
        fetch_id = str(uuid4())
        self.connection.execute(
            "INSERT INTO frontier_science_fetches(fetch_id,created_at,record_json) VALUES(?,?,?)",
            (fetch_id, _utc_now(), json.dumps(record, ensure_ascii=False)),
        )
        self.connection.commit()
        return {**record, "fetch_id": fetch_id, "navigation": literature_navigation(record)}

    def save_evidence(self, record: dict[str, Any]) -> dict[str, Any]:
        record = dict(record)
        if "fetch_id" in record:
            row = self.connection.execute(
                "SELECT record_json FROM frontier_science_fetches WHERE fetch_id=?",
                (record["fetch_id"],),
            ).fetchone()
            if row is None:
                raise ValueError("unknown literature fetch_id")
            fetched = json.loads(row["record_json"])
            inherited = {
                "source": fetched.get("source"),
                "identifier": fetched.get("identifier"),
                "reference_url": fetched.get("url") or fetched.get("reference_url"),
                "content_level": fetched.get("content_level"),
                "fetched_record": fetched,
            }
            if fetched.get("title"):
                inherited["title"] = fetched["title"]
            for key, value in inherited.items():
                if value is not None:
                    if key in record and record[key] != value:
                        raise ValueError(f"evidence {key} conflicts with retained fetch")
                    record[key] = value
            record.setdefault("classification", "EXTERNAL_RESEARCH")
        required = {
            "source",
            "reference_url",
            "classification",
            "title",
            "content_level",
            "retained_claims",
            "applicability",
            "limitations",
            "target_ids",
        }
        missing = sorted(required - record.keys())
        if missing:
            raise ValueError(f"evidence record missing: {', '.join(missing)}")
        if record["classification"] not in EVIDENCE_CLASSIFICATIONS:
            raise ValueError(f"unsupported evidence classification: {record['classification']}")
        for key in ("source", "reference_url", "title", "applicability"):
            if not isinstance(record[key], str) or not record[key].strip():
                raise ValueError(f"evidence {key} must be a non-empty string")
        if record["content_level"] not in EVIDENCE_CONTENT_LEVELS:
            raise ValueError(
                "unsupported evidence content_level: " + str(record["content_level"])
            )
        for key in ("retained_claims", "limitations"):
            values = record[key]
            if not isinstance(values, list) or not values or any(
                not isinstance(value, str) or not value.strip() for value in values
            ):
                raise ValueError(f"evidence {key} must be a non-empty array of strings")
        target_ids = record["target_ids"]
        if not isinstance(target_ids, list) or not target_ids or any(
            not isinstance(value, str) or not value.strip() for value in target_ids
        ):
            raise ValueError("evidence target_ids must be a non-empty array of strings")
        if len(target_ids) != len(set(target_ids)):
            raise ValueError("evidence target_ids must contain unique IDs")
        known_targets = self._known_research_target_ids()
        unknown_targets = sorted(set(target_ids) - known_targets)
        if unknown_targets:
            raise ValueError(
                "evidence references unknown target IDs: " + ", ".join(unknown_targets)
            )
        payload_key = (
            "fetched_record"
            if isinstance(record.get("fetched_record"), dict)
            else "source_record"
            if isinstance(record.get("source_record"), dict)
            else None
        )
        if payload_key is None or not record[payload_key]:
            raise ValueError(
                "evidence requires the exact fetched_record or inspected source_record payload"
            )
        if record["classification"] in {"EXTERNAL_RESEARCH", "EXTERNAL_GUIDELINE"}:
            if payload_key != "fetched_record":
                raise ValueError(
                    "scholarly evidence requires the exact fetched_record payload"
                )
            fetched_level = record[payload_key].get("content_level")
            if fetched_level != record["content_level"]:
                raise ValueError(
                    "evidence content_level must match fetched_record.content_level"
                )
            if fetched_level not in {
                "record_with_abstract",
                "full_text",
                "guideline_text",
                "structured_registry_record",
            }:
                raise ValueError("metadata-only scholarly records cannot be retained as read evidence")
            passages = record.get("evidence_passages")
            if not isinstance(passages, list) or not passages:
                raise ValueError("scholarly evidence requires non-empty evidence_passages")
            retained_claims = set(record["retained_claims"])
            passage_claims: set[str] = set()
            for index, passage in enumerate(passages):
                if not isinstance(passage, dict):
                    raise ValueError(f"evidence_passages[{index}] must be an object")
                unknown_passage_fields = set(passage) - {
                    "excerpt", "locator", "supports_claim"
                }
                if unknown_passage_fields:
                    raise ValueError(
                        f"evidence_passages[{index}] has unsupported fields: "
                        + ", ".join(sorted(unknown_passage_fields))
                    )
                for key in ("excerpt", "locator", "supports_claim"):
                    if not isinstance(passage.get(key), str) or not passage[key].strip():
                        raise ValueError(
                            f"evidence_passages[{index}].{key} must be non-empty"
                        )
                if len(passage["excerpt"]) > 1000:
                    raise ValueError("evidence passage excerpts must be at most 1000 characters")
                if passage["supports_claim"] not in retained_claims:
                    raise ValueError(
                        "each evidence passage supports_claim must exactly match a retained claim"
                    )
                passage_claims.add(passage["supports_claim"])
            if passage_claims != retained_claims:
                raise ValueError(
                    "every retained scholarly claim requires at least one evidence passage"
                )
            appraisal = record.get("quality_appraisal")
            if isinstance(appraisal, str) and appraisal.strip():
                # Codex may state the source-bounded assessment in natural language.
                appraisal = {"narrative": appraisal}
                record["quality_appraisal"] = appraisal
            if not isinstance(appraisal, dict):
                raise ValueError("scholarly evidence requires quality_appraisal")
            if set(appraisal) == {"narrative"}:
                if not isinstance(appraisal["narrative"], str) or not appraisal["narrative"].strip():
                    raise ValueError("quality_appraisal narrative must be non-empty")
            else:
                self._validate_quality_appraisal(appraisal)
        return self._store_evidence(record, payload_key)

    @staticmethod
    def _validate_quality_appraisal(appraisal: dict[str, Any]) -> None:
        required_appraisal = {
            "source_type", "population", "methods", "results", "directness", "bias_or_quality_limits",
        }
        missing = sorted(required_appraisal - set(appraisal))
        if missing:
            raise ValueError("quality_appraisal missing: " + ", ".join(missing))
        unknown = sorted(set(appraisal) - required_appraisal)
        if unknown:
            raise ValueError("quality_appraisal has unsupported fields: " + ", ".join(unknown))
        for key in ("source_type", "population", "methods", "results"):
            if not isinstance(appraisal[key], str) or not appraisal[key].strip():
                raise ValueError(f"quality_appraisal.{key} must be non-empty")
        if appraisal["directness"] not in {"direct", "indirect", "very_indirect", "not_applicable"}:
            raise ValueError("quality_appraisal.directness is invalid")
        limits = appraisal["bias_or_quality_limits"]
        if not isinstance(limits, list) or not limits or any(
            not isinstance(value, str) or not value.strip() for value in limits
        ):
            raise ValueError("quality_appraisal.bias_or_quality_limits must be a non-empty string array")

    def _store_evidence(self, record: dict[str, Any], payload_key: str) -> dict[str, Any]:
        if record["classification"] == "EXTERNAL_PRIMARY_SOURCE":
            if payload_key != "source_record" or record["content_level"] != "primary_source_observation":
                raise ValueError(
                    "external primary sources require a primary_source_observation source_record"
                )
        normalized_record = _jsonable(record)
        normalized_record["contract_version"] = 2
        content_hash = canonical_sha256(normalized_record[payload_key])
        supplied_hash = normalized_record.get("content_sha256")
        if supplied_hash is not None and supplied_hash != content_hash:
            raise ValueError("evidence content_sha256 does not match the retained payload")
        normalized_record["content_sha256"] = content_hash
        existing = self.connection.execute(
            """
            SELECT evidence_id,created_at,record_json FROM frontier_science_evidence
            WHERE reference_url=? OR (identifier IS NOT NULL AND source=? AND identifier=?)
            ORDER BY created_at DESC LIMIT 1
            """,
            (record["reference_url"], record["source"], record.get("identifier")),
        ).fetchone()
        if (
            existing is not None
            and canonical_sha256(json.loads(existing["record_json"]))
            == canonical_sha256(normalized_record)
        ):
            return {
                "saved": True,
                "deduplicated": True,
                "evidence_id": existing["evidence_id"],
                "created_at": existing["created_at"],
            }
        evidence_id = str(uuid4())
        created_at = _utc_now()
        self.connection.execute(
            "INSERT INTO frontier_science_evidence(evidence_id,created_at,source,identifier,reference_url,classification,record_json) VALUES(?,?,?,?,?,?,?)",
            (
                evidence_id,
                created_at,
                record["source"],
                record.get("identifier"),
                record["reference_url"],
                record["classification"],
                json.dumps(normalized_record, ensure_ascii=False),
            ),
        )
        self.connection.commit()
        return {"saved": True, "deduplicated": False, "evidence_id": evidence_id, "created_at": created_at}

    def save_footage_observation(self, observation: dict[str, Any]) -> dict[str, Any]:
        validated = _validate_tool_input(FootageObservation, observation)
        saved = self.save_evidence(validated.evidence_record())
        return {
            **saved,
            "content_level": "primary_source_observation",
            "technical_goal_target_id": TECHNICAL_GOAL_TARGET_ID,
        }

    def list_footage_observations(self, *, athlete: str | None = None, limit: int = 50) -> dict[str, Any]:
        if limit < 1 or limit > 500:
            raise ValueError("footage observation limit must be between 1 and 500")
        rows = self.connection.execute(
            """
            SELECT evidence_id,created_at,record_json FROM frontier_science_evidence
            WHERE classification='EXTERNAL_PRIMARY_SOURCE'
            ORDER BY created_at DESC LIMIT ?
            """,
            (limit,),
        ).fetchall()
        observations = []
        for row in rows:
            record = json.loads(row["record_json"])
            if record.get("content_level") != "primary_source_observation":
                continue
            source_record = record.get("source_record", {})
            if athlete and str(source_record.get("athlete", "")).casefold() != athlete.strip().casefold():
                continue
            observations.append({
                "evidence_id": row["evidence_id"], "created_at": row["created_at"],
                "title": record.get("title"), "reference_url": record.get("reference_url"),
                "athlete": source_record.get("athlete"),
                "opponent_or_context": source_record.get("opponent_or_context"),
                "start_seconds": source_record.get("start_seconds"),
                "end_seconds": source_record.get("end_seconds"),
                "observed_actions": source_record.get("observed_actions", []),
                "situational_conditions": source_record.get("situational_conditions", []),
                "repeated_pattern": source_record.get("repeated_pattern"),
            })
        return {"observations": observations, "count": len(observations)}

    def compare_footage_observations(self, evidence_ids: list[str]) -> dict[str, Any]:
        if not isinstance(evidence_ids, list) or len(evidence_ids) < 2:
            raise ValueError("compare_footage_observations requires at least two evidence IDs")
        if len(evidence_ids) != len(set(evidence_ids)):
            raise ValueError("footage evidence IDs must be unique")
        observations = []
        for evidence_id in evidence_ids:
            loaded = self.load_evidence(evidence_id)
            record = loaded["record"]
            if (
                loaded["classification"] != "EXTERNAL_PRIMARY_SOURCE"
                or record.get("content_level") != "primary_source_observation"
            ):
                raise ValueError(f"evidence is not a primary footage observation: {evidence_id}")
            observations.append({"evidence_id": evidence_id, **record["source_record"]})
        action_sets = [set(item["observed_actions"]) for item in observations]
        condition_sets = [set(item["situational_conditions"]) for item in observations]
        shared_actions = sorted(set.intersection(*action_sets))
        shared_conditions = sorted(set.intersection(*condition_sets))
        return {
            "observations": observations,
            "shared_actions_exact": shared_actions,
            "shared_conditions_exact": shared_conditions,
            "all_marked_repeated_pattern": all(item.get("repeated_pattern") is True for item in observations),
            "comparison_boundary": (
                "Exact retained labels only; Codex must judge semantic similarity, opponent-specific variation, and drill implications."
            ),
        }

    def load_evidence(self, evidence_id: str) -> dict[str, Any]:
        row = self.connection.execute(
            "SELECT * FROM frontier_science_evidence WHERE evidence_id=?",
            (evidence_id,),
        ).fetchone()
        if row is None:
            raise KeyError(f"unknown evidence: {evidence_id}")
        return {
            "evidence_id": row["evidence_id"],
            "created_at": row["created_at"],
            "source": row["source"],
            "identifier": row["identifier"],
            "reference_url": row["reference_url"],
            "classification": row["classification"],
            "record": json.loads(row["record_json"]),
        }


    def list_knowledge_sources(self) -> dict[str, Any]:
        return ScientificKnowledgeClient().list_sources()
