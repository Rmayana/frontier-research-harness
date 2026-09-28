"""Optional FTS5 discovery over exact retained originals, without scientific ranking."""
from __future__ import annotations

import re
import sqlite3
from contextlib import closing
from typing import Any

RECORD_ROUTES = {
    "literature_fetch": ("frontier_science_fetches", "fetch_id", "record_json"),
    "evidence": ("frontier_science_evidence", "evidence_id", "record_json"),
    "experiment_output": ("frontier_science_experiments", "experiment_id", "output_json"),
    "research_entry": ("frontier_science_research_entries", "entry_id", "record_json"),
    "numerical_receipt": ("frontier_science_numerical_receipts", "receipt_id", "record_json"),
    "dataset": ("frontier_science_datasets", "dataset_id", "record_json"),
}


def full_text_rows(connection: sqlite3.Connection, record_type: str, query: str,
                   after: int, through: int, limit: int) -> list[Any]:
    """All query words are literal terms. FTS operators are never interpolated."""
    terms = re.findall(r"\w+", query, flags=re.UNICODE)
    if not terms:
        raise ValueError("full_text query must contain searchable words")
    expression = " AND ".join('"' + term.replace('"', '""') + '"' for term in terms)
    table, key, column = RECORD_ROUTES[record_type]
    index = f"{table}_fts"
    exists = connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (index,)
    ).fetchone()
    if exists is None:
        # Searching a legacy or read-only database must not create tables,
        # triggers, or commit a caller's pending transaction. Index only the
        # requested frozen range in a separate ephemeral connection.
        with closing(sqlite3.connect(":memory:")) as scratch:
            scratch.row_factory = sqlite3.Row
            try:
                scratch.execute("CREATE VIRTUAL TABLE records USING fts5(record_id UNINDEXED,content,tokenize='unicode61')")
            except sqlite3.OperationalError as exc:
                raise ValueError("Full-text search requires SQLite FTS5 support") from exc
            source = connection.execute(
                f"SELECT rowid,{key},{column} FROM {table} WHERE rowid>? AND rowid<=? ORDER BY rowid",
                (after, through),
            )
            scratch.executemany("INSERT INTO records(rowid,record_id,content) VALUES(?,?,?)", source)
            return scratch.execute(
                "SELECT rowid AS cursor_id,record_id,content AS original FROM records "
                "WHERE records MATCH ? ORDER BY rowid LIMIT ?", (expression, limit),
            ).fetchall()
    return connection.execute(
        f"SELECT source.rowid AS cursor_id,source.{key} AS record_id,"
        f"source.{column} AS original FROM {table} source JOIN {index} "
        f"ON source.rowid={index}.rowid WHERE {index} MATCH ? "
        "AND source.rowid>? AND source.rowid<=? ORDER BY source.rowid LIMIT ?",
        (expression, after, through, limit),
    ).fetchall()


def first_match_offset(original: str, query: str) -> int:
    for term in re.findall(r"\w+", query, flags=re.UNICODE):
        match = re.search(re.escape(term), original, flags=re.IGNORECASE)
        if match is not None:
            return match.start()
    return 0
