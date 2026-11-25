"""Append-only, local training records. All IDs are scoped to the private database."""
from contextlib import closing, contextmanager
from datetime import date, datetime, timezone
import json
from pathlib import Path
import sqlite3
from typing import Literal

from training_runtime import settings


RecordKind = Literal["question", "evidence", "prediction", "plan", "adoption", "actual", "review"]
KINDS = {"question", "evidence", "prediction", "plan", "adoption", "actual", "review"}
SELECT_RECORDS = """
SELECT r.*, c.id AS corrected_by
FROM record AS r LEFT JOIN record AS c ON c.corrects = r.id
"""


def database_path() -> Path:
    root = Path(settings()["records"])
    if not root.is_absolute() or not root.is_dir():
        raise ValueError("A configured private records directory is required.")
    return root / "training.sqlite3"


@contextmanager
def write_connection():
    with closing(sqlite3.connect(database_path(), timeout=10)) as conn:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS record (
                id INTEGER PRIMARY KEY,
                request_id TEXT NOT NULL UNIQUE,
                topic TEXT NOT NULL,
                kind TEXT NOT NULL,
                body TEXT NOT NULL,
                recorded_at TEXT NOT NULL,
                occurred_on TEXT,
                refs TEXT NOT NULL,
                corrects INTEGER UNIQUE REFERENCES record(id)
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS record_topic ON record(topic, id)")
        yield conn


def clean_text(value: str, name: str, limit: int) -> str:
    if not isinstance(value, str) or not 0 < len(value.strip()) <= limit:
        raise ValueError(f"{name} must contain 1..{limit} characters.")
    return value.strip()


def record_dict(row: sqlite3.Row) -> dict:
    result = dict(row)
    result["refs"] = json.loads(result["refs"])
    result.pop("request_id")
    return result


def append_record(
    topic: str,
    kind: RecordKind,
    body: str,
    request_id: str,
    refs: list[int] | None = None,
    corrects: int | None = None,
    occurred_on: str | None = None,
) -> dict:
    """Store one fact or decision; reuse request_id only for an identical retry.

    Use a consistent topic across sessions. Adoption records reference a plan only
    after the user chooses it. For corrections provide the latest record ID of the
    same topic/kind and the complete replacement contents, including relevant refs.
    occurred_on is the user's event date; recorded_at is assigned by the server.
    """
    topic = clean_text(topic, "topic", 160)
    body = clean_text(body, "body", 8000)
    request_id = clean_text(request_id, "request_id", 160)
    if kind not in KINDS:
        raise ValueError("Unknown record kind.")
    refs = [] if refs is None else refs
    if len(refs) > 100 or any(type(ref) is not int or ref < 1 for ref in refs):
        raise ValueError("refs must contain at most 100 positive record IDs.")
    refs = sorted(set(refs))
    if corrects is not None and (type(corrects) is not int or corrects < 1):
        raise ValueError("corrects must be a positive record ID.")
    if occurred_on is not None and date.fromisoformat(occurred_on).isoformat() != occurred_on:
        raise ValueError("occurred_on must be YYYY-MM-DD.")
    values = {
        "topic": topic, "kind": kind, "body": body, "occurred_on": occurred_on,
        "refs": json.dumps(refs), "corrects": corrects,
    }
    with write_connection() as conn, conn:
        conn.execute("BEGIN IMMEDIATE")
        existing = conn.execute(SELECT_RECORDS + " WHERE r.request_id = ?", (request_id,)).fetchone()
        if existing is not None:
            if any(existing[key] != val for key, val in values.items()):
                raise ValueError("request_id is already associated with different contents.")
            return record_dict(existing)
        if corrects is not None:
            old = conn.execute(SELECT_RECORDS + " WHERE r.id = ?", (corrects,)).fetchone()
            if old is None or old["topic"] != topic or old["kind"] != kind:
                raise ValueError("Correction must refer to the same topic and kind.")
            if old["corrected_by"] is not None:
                raise ValueError(f"Record already corrected; read record {old['corrected_by']}.")
        linked = {}
        if refs:
            marks = ",".join("?" for _ in refs)
            linked = {r["id"]: r for r in conn.execute(
                f"SELECT id, kind, topic FROM record WHERE id IN ({marks})", refs
            )}
            if len(linked) != len(refs):
                raise ValueError("One or more referenced records do not exist.")
        if kind == "adoption" and not any(
            r["kind"] == "plan" and r["topic"] == topic for r in linked.values()
        ):
            raise ValueError("Adoption requires a plan reference from the same topic.")
        row_id = conn.execute("""
            INSERT INTO record(request_id, topic, kind, body, recorded_at, occurred_on, refs, corrects)
            VALUES(:request_id, :topic, :kind, :body, :recorded_at, :occurred_on, :refs, :corrects)
        """, {**values, "request_id": request_id, "recorded_at": datetime.now(timezone.utc).isoformat()}).lastrowid
        return record_dict(conn.execute(SELECT_RECORDS + " WHERE r.id = ?", (row_id,)).fetchone())


def read_record(
    topic: str | None = None,
    record_id: int | None = None,
    before_id: int | None = None,
    limit: int = 20,
) -> dict:
    """Read exact historical records or discover recent topics. Newest IDs first.

    Use next_before_id to continue the same list. A corrected_by field identifies
    the next correction; read its ID to get the updated contents.
    """
    if not 1 <= limit <= 50:
        raise ValueError("limit must be 1..50.")
    if record_id is not None and (topic is not None or before_id is not None):
        raise ValueError("Use record_id alone for exact retrieval.")
    terms, params = [], []
    if topic is not None:
        terms.append("r.topic = ?")
        params.append(clean_text(topic, "topic", 160))
    for value, test in ((record_id, "r.id = ?"), (before_id, "r.id < ?")):
        if value is not None:
            if type(value) is not int or value < 1:
                raise ValueError("IDs must be positive integers.")
            terms.append(test)
            params.append(value)
    where = " WHERE " + " AND ".join(terms) if terms else ""
    path = database_path()
    if not path.is_file():
        return {"records": [], "next_before_id": None}
    with closing(sqlite3.connect(path.as_uri() + "?mode=ro", uri=True, timeout=10)) as conn:
        conn.row_factory = sqlite3.Row
        # A concurrent first append can create the file before the schema exists.
        if not conn.execute("SELECT 1 FROM sqlite_schema WHERE type='table' AND name='record'").fetchone():
            return {"records": [], "next_before_id": None}
        rows = conn.execute(SELECT_RECORDS + where + " ORDER BY r.id DESC LIMIT ?", [*params, limit + 1]).fetchall()
    page = rows[:limit]
    return {"records": [record_dict(row) for row in page],
            "next_before_id": page[-1]["id"] if len(rows) > limit else None}
