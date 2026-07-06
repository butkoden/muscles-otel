# Muscles OpenTelemetry

Observability hooks and a neutral telemetry provider for Muscles lifecycle
instrumentation.

This package traces real framework lifecycle points: strategy execution, server
dispatch, action dispatch, validation, rules/security and handler execution. The
current implementation ships an in-memory `MusclesTracer` that implements the
core `TelemetryProvider` interface. It does not configure an OpenTelemetry SDK,
OTLP exporter, collector or vendor backend by itself.

## What This Package Is For

Use `muscles-otel` when a Muscles application or framework package needs a
single tracing surface without importing an observability vendor directly:

- applications install `OtelPackage` once during bootstrap;
- other packages call `resolve_telemetry(app)` from `muscles`;
- spans are recorded only when tracing is enabled;
- sensitive attributes are redacted before they reach span records.

This keeps instrumentation optional. If `muscles-otel` is not installed, core
falls back to `NoopTelemetry`, so package code can keep the same tracing calls.

## What It Is Not Yet

`muscles-otel` is not yet a full OpenTelemetry distribution. It currently does
not export traces to Jaeger, Tempo, Honeycomb, Datadog or an OTLP collector. A
production exporter can be added behind the same `TelemetryProvider` surface
without changing packages that already use `resolve_telemetry(app)`.

## Related Repositories

- [`muscles`](https://github.com/butkoden/muscles) - core lifecycle, context, actions and dispatcher hooks.
- [`muscles-asgi`](https://github.com/butkoden/muscles-asgi) - ASGI runtime spans and server dispatch surfaces.
- [`muscles-wsgi`](https://github.com/butkoden/muscles-wsgi) - WSGI runtime spans and server dispatch surfaces.
- [`muscles-sql`](https://github.com/butkoden/muscles-sql) - SQL flows that can be traced by application instrumentation.
- [`muscles-benchmarks`](https://github.com/butkoden/muscles-benchmarks) - observability overhead regression checks.

## Concept Guardrails

- Observability must follow the Muscles application model and inspect contract,
  not individual transport implementation details only.
- A trace should show the same use case across ASGI, WSGI, CLI, SQL, MCP,
  JSON-RPC, and future adapters.
- Instrumentation must be optional and low overhead when disabled.
- Do not couple the framework to one vendor.
- Sensitive data must be redacted by default.
- Instrumentation must not own business dispatch or call handlers twice.

## Initial Goal

Provide opt-in tracing helpers and strategy/server/action hooks for core Muscles
lifecycle events with tests proving that disabled instrumentation is cheap and
enabled instrumentation explains real action flow.

## Current Stage (Issue #1)

Implemented opt-in lifecycle instrumentation:

- disabled mode: no span allocation and zero records;
- enabled mode: span duration and attributes are captured.
- package lifecycle entry point: `init_package(app, config)` installs
  `OtelPackage` through Muscles core lifecycle;
- provider registration: enabled tracer is registered as the neutral
  `TelemetryProvider` service, so other packages only depend on `muscles`;
- `OtelStrategyMixin` for `muscles.strategy.execute`;
- `OtelContextMixin` for `muscles.context.execute`;
- `instrument_server_dispatch()` for `muscles.server.dispatch`;
- `instrument_action_dispatch()` for:
  - `muscles.action.execute`;
  - `muscles.action.validate`;
  - `muscles.action.rules`;
  - `muscles.action.handler`;
- error status/events for validation, permission, and execution failures;
- sensitive attribute redaction by default.

Implementation note: action lifecycle spans currently mirror the core
dispatcher phases through the available dispatcher methods. A future core hook
API can replace this with official callbacks without changing the public
instrumentation surface.

## Package Lifecycle Provider

Applications should install `muscles-otel` as an optional framework package:

```python
from muscles import (
    TelemetryProvider,
    doctor_application,
    inspect_application,
    install_package,
)
from muscles_otel import OtelPackage, init_package

app = App()
tracer = install_package(app, {"enabled": True}, OtelPackage())

telemetry = app.container.resolve(TelemetryProvider)
assert telemetry is tracer

contract = inspect_application(app)
doctor = doctor_application(app)
```

`init_package(app, config)` remains available for legacy auto-package loaders
and delegates to the same core lifecycle installer.

Framework packages such as `muscles-ai` and `muscles-documents` must not import
`muscles_otel` directly. They resolve telemetry through Muscles core:

```python
from muscles import resolve_telemetry

telemetry = resolve_telemetry(app)
with telemetry.span("muscles.package.operation"):
    ...
```

When this package is not installed, core returns `NoopTelemetry`.

Inspection reports the installed `otel` package and a safe capability payload:

```python
from muscles import inspect_application, doctor_application

inspect_application(app)["capabilities"]["otel"]
# {"provider": "MusclesTracer", "enabled": True, "records.count": 0}

doctor_application(app)["packages"]["otel"]
# {"status": "ok", "checks": [{"name": "otel.telemetry_provider", ...}]}
```

## Direct Instrumentation Helpers

The package also exposes mixins and helper functions for integration points that
already own a concrete dispatch call:

- `OtelContextMixin` for `muscles.context.execute`;
- `OtelStrategyMixin` for `muscles.strategy.execute`;
- `instrument_server_dispatch(...)` for server/request boundaries;
- `instrument_action_dispatch(...)` for action validation, rules and handler
  spans.

Use these helpers at runtime boundaries. Business packages should usually use
only `resolve_telemetry(app)` and neutral span names.

### Run tests

```bash
python -m pytest -q
```

When testing against local core changes:

```bash
PYTHONPATH=../muscles/src:src python -m pytest -q
```

User docs:

- English: [docs/otel-lifecycle.en.md](docs/otel-lifecycle.en.md)
- Русский: [docs/otel-lifecycle.ru.md](docs/otel-lifecycle.ru.md)
