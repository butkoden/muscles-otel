from __future__ import annotations

"""Lifecycle provider example for muscles-otel.

Run:
  PYTHONPATH=src python examples/run_package_lifecycle.py
"""

from types import SimpleNamespace

from muscles import TelemetryProvider
from muscles_otel import init_package


def main() -> None:
    app = SimpleNamespace()
    tracer = init_package(app, {"enabled": True})

    telemetry = app.container.resolve(TelemetryProvider)
    if telemetry is not tracer:
        raise RuntimeError("TelemetryProvider was not registered")

    with telemetry.span("example.lifecycle", **{"safe.count": 1, "prompt": "redacted"}):
        pass

    print("records ->", len(tracer.records))
    print("attributes ->", tracer.records[-1].attributes)


if __name__ == "__main__":
    main()
