from __future__ import annotations

from pathlib import Path

from evallib.cli import main
from evallib.jsonl import write_jsonl
from evallib.schema import Trace, Turn, Role


def _make_trace(query_id: str) -> Trace:
    return Trace(
        query_id=query_id,
        turns=[Turn(role=Role.user, content="hi")],
        final_response="hello",
    )


def test_validate_all_valid_returns_zero(tmp_path: Path) -> None:
    path = tmp_path / "traces.jsonl"
    write_jsonl([_make_trace("q-1"), _make_trace("q-2")], path)

    exit_code = main(["validate", "--model", "trace", "--file", str(path)])

    assert exit_code == 0


def test_validate_malformed_line_returns_nonzero(tmp_path: Path) -> None:
    path = tmp_path / "traces.jsonl"
    with path.open("w", encoding="utf-8") as f:
        f.write(_make_trace("q-1").model_dump_json() + "\n")
        f.write('{"query_id": "q-2"}\n')  # missing required fields

    exit_code = main(["validate", "--model", "trace", "--file", str(path)])

    assert exit_code == 1


def test_validate_missing_file_returns_two(tmp_path: Path) -> None:
    exit_code = main(
        ["validate", "--model", "trace", "--file", str(tmp_path / "nope.jsonl")]
    )
    assert exit_code == 2
