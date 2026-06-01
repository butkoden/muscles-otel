# Muscles OpenTelemetry

OpenTelemetry lifecycle instrumentation for Muscles production observability.

This package makes Muscles credible in production by tracing real framework
lifecycle points: strategy execution, server dispatch, action dispatch,
validation, rules/security, and handler execution.

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
- `OtelStrategyMixin` for `muscles.strategy.execute`;
- `instrument_server_dispatch()` for `muscles.server.dispatch`;
- `instrument_action_dispatch()` for:
  - `muscles.action.execute`;
  - `muscles.action.validate`;
  - `muscles.action.rules`;
  - `muscles.action.handler`;
- error status/events for validation, permission, and execution failures;
- sensitive attribute redaction by default.

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
