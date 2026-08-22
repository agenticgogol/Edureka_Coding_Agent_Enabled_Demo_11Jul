"""Base class for normalizing traces from any source into evallib.schema.Trace.

A concrete adapter (LangSmith, Phoenix, raw JSON log, ...) implements
`iter_raw_records` and `to_trace`. Everything downstream in the eval suite
only ever sees `Trace` objects, so a new source is a new adapter, not a
change to any skill.
"""

from __future__ import annotations

import abc
from typing import Any, Iterator

from evallib.schema import Trace


class TraceAdapter(abc.ABC):
    """Subclass per source system. Instances are stateless / reusable."""

    @abc.abstractmethod
    def iter_raw_records(self, source: Any) -> Iterator[Any]:
        """Yield one raw, source-native record at a time from `source`
        (a file path, client handle, API response, etc.)."""
        raise NotImplementedError

    @abc.abstractmethod
    def to_trace(self, raw_record: Any) -> Trace:
        """Convert one raw, source-native record into a Trace. Must raise
        (not silently drop fields) if the raw record is missing data the
        Trace schema requires."""
        raise NotImplementedError

    def normalize(self, source: Any) -> list[Trace]:
        """Convenience: adapt every record from `source` into a list of
        Trace objects."""
        return [self.to_trace(raw) for raw in self.iter_raw_records(source)]
