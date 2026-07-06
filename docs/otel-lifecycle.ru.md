# OpenTelemetry lifecycle instrumentation

`muscles-otel` инструментирует реальные lifecycle точки Muscles. Это не
отдельный business dispatch layer и не собственная routing/action/validation/
permissions model.

## Context и strategy execution

Используйте `OtelContextMixin` вместе с `muscles.core.Context`, чтобы
инструментировать полный lifecycle `Context.execute`:

```python
class TracedContext(OtelContextMixin, Context):
    pass
```

Передача `otel_tracer=tracer` в `context.execute(...)` создает span
`muscles.context.execute` и передает тот же tracer в strategy.

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

Stage note: action phase spans сейчас повторяют доступные фазы core dispatcher.
В будущем лучше заменить это на официальный core hook API.

## Sensitive data

Sensitive attributes вроде tokens, passwords, API keys, authorization headers и
payloads, prompts, queries, documents, chunks, content, body, HTML и text values
редактируются по умолчанию.

## Framework package provider

`muscles-otel` можно подключить через общий package lifecycle Muscles:

```python
from muscles import TelemetryProvider
from muscles_otel import init_package

tracer = init_package(app, {"enabled": True})
telemetry = app.container.resolve(TelemetryProvider)
```

Tracer реализует нейтральную поверхность `TelemetryProvider.span(...)`.
Остальные пакеты получают telemetry через `muscles` core и не импортируют
`muscles_otel` напрямую.
