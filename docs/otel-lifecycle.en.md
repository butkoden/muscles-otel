# OpenTelemetry Lifecycle Instrumentation

`muscles-otel` instruments real Muscles lifecycle points. It is not a separate
business dispatch layer and does not define its own routing, action, validation,
or permissions model.

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
and payload values are redacted by default.
