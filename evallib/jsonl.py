"""Generic JSONL round-trip helpers for any StrictModel in schema.py."""

from __future__ import annotations

from pathlib import Path
from typing import TypeVar

from pydantic import BaseModel

M = TypeVar("M", bound=BaseModel)


def write_jsonl(records: list[M], path: str | Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for record in records:
            f.write(record.model_dump_json())
            f.write("\n")


def append_jsonl(record: M, path: str | Path) -> None:
    """Appends one record as a new line — never overwrites existing rows.
    For an append-only log (e.g. MetricsHistoryRecord) where every writer
    across every run must accumulate history rather than each call
    clobbering the last one, unlike write_jsonl's full-file replace."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(record.model_dump_json())
        f.write("\n")


def read_jsonl(model: type[M], path: str | Path) -> list[M]:
    path = Path(path)
    records: list[M] = []
    with path.open("r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                records.append(model.model_validate_json(line))
            except Exception as exc:  # re-raise with line context
                raise ValueError(
                    f"{path}:{line_no}: invalid {model.__name__} record: {exc}"
                ) from exc
    return records
