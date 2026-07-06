# OpenTelemetry lifecycle instrumentation

`muscles-otel` инструментирует реальные lifecycle точки Muscles. Это не
отдельный business dispatch layer и не собственная routing/action/validation/
permissions model.

Сейчас пакет предоставляет in-memory tracer `MusclesTracer` и integration
helpers. Он реализует нейтральный интерфейс `TelemetryProvider` из `muscles`,
но сам по себе не настраивает OpenTelemetry SDK, OTLP exporter, collector или
vendor backend.

## Подключение в приложении

Устанавливайте пакет один раз во время bootstrap приложения:

```python
from muscles import TelemetryProvider, install_package
from muscles_otel import OtelPackage

app = App()
tracer = install_package(app, {"enabled": True}, OtelPackage())

assert app.container.resolve(TelemetryProvider) is tracer
```

`enabled=False` - дешевый режим по умолчанию: spans не создают records.
Используйте `enabled=True` там, где нужно собирать span records: в тестах,
локальной разработке или production-окружении с будущим exporter.

`init_package(app, config)` остается доступным для legacy package loaders и
делегирует установку в общий lifecycle core, если `muscles` доступен.

## Использование из других пакетов

Framework packages не должны импортировать `muscles_otel` напрямую. Им нужен
только core-контракт telemetry:

```python
from muscles import resolve_telemetry

telemetry = resolve_telemetry(app)
with telemetry.span("documents.search", **{"safe.count": 3}):
    ...
```

Если `muscles-otel` не установлен, `resolve_telemetry(app)` вернет
`NoopTelemetry`, и код продолжит работать.

## Inspect и doctor

После установки core tooling видит пакет:

```python
from muscles import doctor_application, inspect_application

inspect_application(app)["packages"]
# [{"namespace": "otel", "name": "OtelPackage"}]

inspect_application(app)["capabilities"]["otel"]
# {"provider": "MusclesTracer", "enabled": True, "records.count": 0}

doctor_application(app)["packages"]["otel"]["status"]
# "ok"
```

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

## Legacy shortcut `init_package`

Legacy auto-package loaders могут по-прежнему вызывать
`init_package(app, config)`. Если `muscles` core доступен, используется тот же
lifecycle installer:

```python
from muscles import TelemetryProvider
from muscles_otel import init_package

tracer = init_package(app, {"enabled": True})
telemetry = app.container.resolve(TelemetryProvider)
```

В новом bootstrap-коде приложения лучше использовать
`install_package(app, config, OtelPackage())`, потому что так lifecycle виден
явно.
