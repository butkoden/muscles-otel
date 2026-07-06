# Muscles OpenTelemetry

OpenTelemetry lifecycle instrumentation for Muscles production observability.

This package makes Muscles credible in production by tracing real framework
lifecycle points: strategy execution, server dispatch, action dispatch,
validation, rules/security, and handler execution.

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
from types import SimpleNamespace

from muscles import TelemetryProvider
from muscles_otel import init_package

app = SimpleNamespace()
tracer = init_package(app, {"enabled": True})

telemetry = app.container.resolve(TelemetryProvider)
assert telemetry is tracer
```

Framework packages such as `muscles-ai` and `muscles-documents` must not import
`muscles_otel` directly. They resolve telemetry through Muscles core:

```python
from muscles import resolve_telemetry

telemetry = resolve_telemetry(app)
with telemetry.span("muscles.package.operation"):
    ...
```

When this package is not installed, core returns `NoopTelemetry`.

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
