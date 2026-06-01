from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from time import perf_counter
from typing import Any, Iterator


@dataclass(frozen=True)
class SpanRecord:
    name: str
    duration_ms: float
    attributes: dict[str, Any]


class MusclesTracer:
    def __init__(self, enabled: bool = False) -> None:
        self.enabled = enabled
        self.records: list[SpanRecord] = []

    @contextmanager
    def span(self, name: str, **attributes: Any) -> Iterator[None]:
        if not self.enabled:
            yield
            return
        started = perf_counter()
        try:
            yield
        finally:
            duration_ms = (perf_counter() - started) * 1000.0
            self.records.append(SpanRecord(name=name, duration_ms=duration_ms, attributes=attributes))

    def instrument_call(self, span_name: str, callback, **attributes: Any):
        with self.span(span_name, **attributes):
            return callback()
