# OpenTelemetry lifecycle instrumentation

`muscles-otel` инструментирует реальные lifecycle точки Muscles. Это не
отдельный business dispatch layer и не собственная routing/action/validation/
permissions model.

## Strategy execution

Используйте `OtelStrategyMixin` вместе с конкретной strategy:

```python
class TracedStrategy(OtelStrategyMixin, MyStrategy):
    pass
```

Передача `otel_tracer=tracer` создает span `muscles.strategy.execute`.

## Server dispatch

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

Это создает `muscles.server.dispatch` с route и transport attributes.

## Action dispatch

```python
result = instrument_action_dispatch(
    tracer,
    app,
    action_name="bookings.create",
    payload={"title": "Call"},
    transport="mcp",
)
```

Helper записывает:

- `muscles.action.validate`;
- `muscles.action.rules`;
- `muscles.action.handler`;
- `muscles.action.execute`.

Validation, rules/security и handler execution остаются в Muscles core.
Instrumentation не должна вызывать handler больше одного раза.

## Sensitive data

Sensitive attributes вроде tokens, passwords, API keys, authorization headers и
payload values редактируются по умолчанию.
