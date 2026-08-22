from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from evallib.adapters import RawJSONAdapter, TraceAdapter
from evallib.schema import Trace

RAW_RECORDS = [
    {
        "query_id": "q-1",
        "dimension_tuple": ["billing"],
        "turns": [
            {"role": "user", "content": "refund please"},
            {"role": "assistant", "content": "sure, done"},
        ],
        "final_response": "sure, done",
        "metadata": {"source": "raw_json"},
    },
    {
        "query_id": "q-2",
        "turns": [{"role": "user", "content": "hello"}],
        "final_response": "hi there",
    },
]


@pytest.fixture
def raw_log_file(tmp_path: Path) -> Path:
    path = tmp_path / "raw_log.json"
    path.write_text(json.dumps(RAW_RECORDS), encoding="utf-8")
    return path


def test_raw_json_adapter_is_a_trace_adapter() -> None:
    assert issubclass(RawJSONAdapter, TraceAdapter)


def test_raw_json_adapter_normalizes_to_traces(raw_log_file: Path) -> None:
    traces = RawJSONAdapter().normalize(raw_log_file)
    assert len(traces) == 2
    assert all(isinstance(t, Trace) for t in traces)
    assert traces[0].query_id == "q-1"
    assert traces[0].dimension_tuple == ("billing",)
    assert traces[1].metadata == {}


def test_raw_json_adapter_rejects_non_array(tmp_path: Path) -> None:
    path = tmp_path / "not_a_list.json"
    path.write_text(json.dumps({"query_id": "q-1"}), encoding="utf-8")
    with pytest.raises(ValueError):
        list(RawJSONAdapter().iter_raw_records(path))


def test_raw_json_adapter_malformed_record_raises(tmp_path: Path) -> None:
    path = tmp_path / "malformed.json"
    path.write_text(json.dumps([{"query_id": "q-1"}]), encoding="utf-8")  # no turns/final_response
    adapter = RawJSONAdapter()
    with pytest.raises(ValidationError):
        adapter.normalize(path)
