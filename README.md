# Muscles OpenTelemetry

OpenTelemetry integration for Muscles production observability.

This package should make Muscles credible in production by tracing request,
action, rule, SQL, CLI, and protocol adapter execution through one shared
observability model.

## Concept Guardrails

- Observability must follow the Muscles application model, not individual
  transport implementation details only.
- A trace should show the same use case across ASGI, WSGI, CLI, SQL, MCP,
  JSON-RPC, and future adapters.
- Instrumentation must be optional and low overhead when disabled.
- Do not couple the framework to one vendor.
- Sensitive data must be redacted by default.

## Initial Goal

Provide opt-in tracing helpers and middleware/hooks for core Muscles lifecycle
events with tests proving that disabled instrumentation is cheap.

## Current Stage (Issue #1)

Implemented opt-in lifecycle tracer:

- disabled mode: no span allocation and zero records;
- enabled mode: span duration and attributes are captured.

### Run tests

```bash
python -m pytest -q
```
