# OpenTelemetry Lifecycle Instrumentation

`muscles-otel` instruments real Muscles lifecycle points. It is not a separate
business dispatch layer and does not define its own routing, action, validation,
or permissions model.

The package currently provides an in-memory `MusclesTracer` plus integration
helpers. It implements the neutral `TelemetryProvider` surface from `muscles`;
it does not configure an OpenTelemetry SDK, OTLP exporter, collector or vendor
backend by itself.

## Install In An Application

Install the package once during application bootstrap:

```python
from muscles import TelemetryProvider, install_package
from muscles_otel import OtelPackage

app = App()
tracer = install_package(app, {"enabled": True}, OtelPackage())

assert app.container.resolve(TelemetryProvider) is tracer
```

`enabled=False` is the cheap default mode: spans allocate no records. Use
`enabled=True` in tests or local/dev/prod environments where span collection is
expected.

`init_package(app, config)` remains available for legacy package loaders and
delegates to the same lifecycle installer when `muscles` core is available.

## Use From Other Packages

Framework packages should not import `muscles_otel` directly. They should depend
only on the core telemetry contract:

```python
from muscles import resolve_telemetry

telemetry = resolve_telemetry(app)
with telemetry.span("documents.search", **{"safe.count": 3}):
    ...
```

If `muscles-otel` is not installed, `resolve_telemetry(app)` returns
`NoopTelemetry` and the code still runs.

## Inspect And Doctor

After installation, core tooling can discover the package:

```python
from muscles import doctor_application, inspect_application

inspect_application(app)["packages"]
# [{"namespace": "otel", "name": "OtelPackage"}]

inspect_application(app)["capabilities"]["otel"]
# {"provider": "MusclesTracer", "enabled": True, "records.count": 0}

doctor_application(app)["packages"]["otel"]["status"]
# "ok"
```

## Context And Strategy Execution

Use `OtelContextMixin` with `muscles.core.Context` to instrument the full
`Context.execute` lifecycle:

```python
class TracedContext(OtelContextMixin, Context):
    pass
```

Passing `otel_tracer=tracer` to `context.execute(...)` creates a
`muscles.context.execute` span and passes the same tracer to the strategy.

Use `OtelStrategyMixin` with a concrete strategy:

```python
class TracedStrategy(OtelStrategyMixin, MyStrategy):
    pass
```

Passing `otel_tracer=tracer` creates a `muscles.strategy.execute` span.

## Server Dispatch

```python
result = instrument_server_dispatch(
    tracer,
    lambda: server.dispatch(request),
    app_name="BookingApp",
    route_name="bookings.create",
    route_path="/bookings",
    transport="jsonrpc",
)
```

This creates `muscles.server.dispatch` with route and transport attributes.

## Action Dispatch

```python
result = instrument_action_dispatch(
    tracer,
    app,
    action_name="bookings.create",
    payload={"title": "Call"},
    transport="mcp",
)
```

The helper records:

- `muscles.action.validate`;
- `muscles.action.rules`;
- `muscles.action.handler`;
- `muscles.action.execute`.

Validation, rules/security, and handler execution still use Muscles core.
Instrumentation must not call the handler more than once.

Stage note: action phase spans currently mirror the available core dispatcher
phases. A future core hook API should replace this with official callbacks.

## Sensitive Data

Sensitive attributes such as tokens, passwords, API keys, authorization headers,
payloads, prompts, queries, documents, chunks, content, body, HTML and text
values are redacted by default.

## Legacy `init_package` Shortcut

Legacy auto-package loaders may still call `init_package(app, config)`. It uses
the same lifecycle installer when `muscles` core is present:

```python
from muscles import TelemetryProvider
from muscles_otel import init_package

tracer = init_package(app, {"enabled": True})
telemetry = app.container.resolve(TelemetryProvider)
```

Prefer `install_package(app, config, OtelPackage())` in new application
bootstrap code because it makes the lifecycle explicit.
