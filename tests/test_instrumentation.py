from contextlib import contextmanager

import pytest

from muscles.core import (
    ActionDispatcher,
    ActionPermissionDenied,
    ActionValidationError,
    ApplicationMeta,
    BaseStrategy,
    Context,
    register_action,
)

from muscles_otel import (
    MusclesTracer,
    OtelContextMixin,
    OtelStrategyMixin,
    SpanRecord,
    instrument_action_dispatch,
    instrument_server_dispatch,
)


class _EchoStrategy(BaseStrategy):
    def execute(self, *args, **kwargs):
        return kwargs.get("value", "ok")


class _TracedStrategy(OtelStrategyMixin, _EchoStrategy):
    pass


class _TracedContext(OtelContextMixin, Context):
    pass


class _App(metaclass=ApplicationMeta):
    context = Context(_EchoStrategy)


class _SpanOnlyTelemetry:
    def __init__(self):
        self.records = []

    @contextmanager
    def span(self, name, **attributes):
        span_attributes = dict(attributes)
        yield span_attributes
        self.records.append((name, span_attributes))


BOOKING_INPUT_SCHEMA = {
    "type": "object",
    "properties": {"title": {"type": "string"}},
    "required": ["title"],
}


def _build_app(handler=None, rules=None, strategy=None):
    class _LocalApp(metaclass=ApplicationMeta):
        context = Context(strategy or _EchoStrategy)

    app = _LocalApp()

    def default_handler(payload, context):
        return {"title": payload["title"], "transport": context.transport}

    register_action(
        app,
        name="bookings.create",
        input_schema=BOOKING_INPUT_SCHEMA,
        rules=rules or [],
        transports=["http", "mcp", "jsonrpc"],
        handler=handler or default_handler,
    )
    return app


def test_disabled_tracer_has_no_records():
    tracer = MusclesTracer(enabled=False)
    value = tracer.instrument_call("muscles.action.execute", lambda: 42, action="bookings.create")
    assert value == 42
    assert tracer.records == []


def test_enabled_tracer_records_span_without_sensitive_payload():
    tracer = MusclesTracer(enabled=True)
    tracer.instrument_call(
        "muscles.action.execute",
        lambda: "ok",
        **{
            "muscles.action.name": "bookings.create",
            "secret.token": "hidden",
            "payload": {"password": "secret"},
        },
    )

    assert len(tracer.records) == 1
    record = tracer.records[0]
    assert record.name == "muscles.action.execute"
    assert record.attributes["muscles.action.name"] == "bookings.create"
    assert "secret.token" not in record.attributes
    assert "payload" not in record.attributes
    assert record.duration_ms >= 0


def test_enabled_span_context_allows_safe_attribute_enrichment():
    tracer = MusclesTracer(enabled=True)

    with tracer.span("muscles.server.dispatch", **{"http.route": "/ready"}) as attributes:
        attributes["http.status_code"] = 200
        attributes["authorization"] = "hidden"

    assert tracer.records[0].attributes == {
        "http.route": "/ready",
        "http.status_code": 200,
    }


def test_extended_rag_sensitive_attributes_are_redacted():
    tracer = MusclesTracer(enabled=True)
    tracer.instrument_call(
        "muscles.ai.generate",
        lambda: "ok",
        **{
            "prompt": "hidden",
            "query": "hidden",
            "document.id": "hidden",
            "chunk.index": 1,
            "content": "hidden",
            "body": "hidden",
            "html": "<p>hidden</p>",
            "text": "hidden",
            "ai.provider": "noop",
        },
    )

    assert tracer.records[0].attributes == {"ai.provider": "noop"}


def test_redaction_keeps_safe_plural_document_attributes():
    tracer = MusclesTracer(enabled=True)
    tracer.instrument_call(
        "muscles.documents.chunk",
        lambda: "ok",
        **{
            "documents.source": "docs",
            "documents.chunker": "fixed",
            "ai.documents.retrieved": 3,
            "document.text": "hidden",
            "chunk.text": "hidden",
        },
    )

    assert tracer.records[0].attributes == {
        "documents.source": "docs",
        "documents.chunker": "fixed",
        "ai.documents.retrieved": 3,
    }


def test_strategy_mixin_creates_strategy_execute_span():
    tracer = MusclesTracer(enabled=True)
    strategy = _TracedStrategy()

    result = strategy.execute(value="ok", otel_tracer=tracer, container=_App())

    assert result == "ok"
    assert [record.name for record in tracer.records] == ["muscles.strategy.execute"]
    assert tracer.records[0].attributes["muscles.strategy"] == "_TracedStrategy"
    assert tracer.records[0].attributes["muscles.app"] == "_App"


def test_strategy_mixin_uses_neutral_span_provider_without_instrument_call():
    telemetry = _SpanOnlyTelemetry()
    strategy = _TracedStrategy()

    result = strategy.execute(value="ok", otel_tracer=telemetry, container=_App())

    assert result == "ok"
    assert telemetry.records == [
        (
            "muscles.strategy.execute",
            {"muscles.app": "_App", "muscles.strategy": "_TracedStrategy"},
        )
    ]


def test_context_mixin_creates_context_execute_span_and_passes_tracer_to_strategy():
    tracer = MusclesTracer(enabled=True)
    context = _TracedContext(_TracedStrategy, params={"value": "ok"})
    context.set_container(_App())

    result = context.execute(otel_tracer=tracer)

    assert result == "ok"
    assert [record.name for record in tracer.records] == [
        "muscles.strategy.execute",
        "muscles.context.execute",
    ]
    context_span = tracer.records[-1]
    assert context_span.attributes["muscles.app"] == "_App"
    assert context_span.attributes["muscles.strategy"] == "_TracedStrategy"


def test_server_dispatch_creates_server_span_with_route_attributes():
    tracer = MusclesTracer(enabled=True)

    result = instrument_server_dispatch(
        tracer,
        lambda: {"ok": True},
        app_name="BookingApp",
        route_name="bookings.create",
        route_path="/bookings",
        transport="jsonrpc",
    )

    assert result == {"ok": True}
    assert tracer.records[0].name == "muscles.server.dispatch"
    assert tracer.records[0].attributes["muscles.route.name"] == "bookings.create"
    assert tracer.records[0].attributes["muscles.route.path"] == "/bookings"
    assert tracer.records[0].attributes["muscles.transport"] == "jsonrpc"


def test_action_dispatch_records_execute_validate_rules_handler_spans():
    tracer = MusclesTracer(enabled=True)
    app = _build_app()

    result = instrument_action_dispatch(
        tracer,
        app,
        action_name="bookings.create",
        payload={"title": "Call"},
        transport="mcp",
    )

    assert result.value == {"title": "Call", "transport": "mcp"}
    assert [record.name for record in tracer.records] == [
        "muscles.action.validate",
        "muscles.action.rules",
        "muscles.action.handler",
        "muscles.action.execute",
    ]
    execute_span = tracer.records[-1]
    assert execute_span.attributes["muscles.action.name"] == "bookings.create"
    assert execute_span.attributes["muscles.app"] == "_LocalApp"
    assert execute_span.attributes["muscles.runtime_mode"] in {"development", "test", "production"}
    assert execute_span.attributes["muscles.transport"] == "mcp"
    assert execute_span.attributes["muscles.result.type"] == "dict"


def test_action_dispatch_calls_handler_once():
    tracer = MusclesTracer(enabled=True)
    calls = []

    def create_booking(payload, context):
        calls.append(payload)
        return {"title": payload["title"]}

    app = _build_app(handler=create_booking)

    instrument_action_dispatch(
        tracer,
        app,
        action_name="bookings.create",
        payload={"title": "Call"},
        transport="mcp",
    )

    assert calls == [{"title": "Call"}]


def test_action_validation_error_is_visible_in_span_status():
    tracer = MusclesTracer(enabled=True)
    app = _build_app()

    with pytest.raises(ActionValidationError):
        instrument_action_dispatch(
            tracer,
            app,
            action_name="bookings.create",
            payload={},
            transport="mcp",
        )

    validate_span = tracer.find("muscles.action.validate")[0]
    execute_span = tracer.find("muscles.action.execute")[0]
    assert validate_span.status == "error"
    assert validate_span.attributes["error.type"] == "ActionValidationError"
    assert execute_span.status == "error"


def test_action_permission_denied_is_visible_in_rules_span():
    tracer = MusclesTracer(enabled=True)

    def deny(payload, context):
        return False

    app = _build_app(rules=[deny])

    with pytest.raises(ActionPermissionDenied):
        instrument_action_dispatch(
            tracer,
            app,
            action_name="bookings.create",
            payload={"title": "Call"},
            transport="mcp",
        )

    rules_span = tracer.find("muscles.action.rules")[0]
    execute_span = tracer.find("muscles.action.execute")[0]
    assert rules_span.status == "error"
    assert rules_span.attributes["error.type"] == "ActionPermissionDenied"
    assert execute_span.status == "error"


def test_instrumentation_state_is_scoped_to_tracer_instance():
    tracer_a = MusclesTracer(enabled=True)
    tracer_b = MusclesTracer(enabled=True)

    tracer_a.instrument_call("muscles.strategy.execute", lambda: "a", **{"muscles.app": "A"})
    tracer_b.instrument_call("muscles.strategy.execute", lambda: "b", **{"muscles.app": "B"})

    assert tracer_a.records[0].attributes["muscles.app"] == "A"
    assert tracer_b.records[0].attributes["muscles.app"] == "B"
    assert tracer_a.records is not tracer_b.records


def test_span_record_has_error_events_without_sensitive_values():
    tracer = MusclesTracer(enabled=True)

    with pytest.raises(RuntimeError):
        tracer.instrument_call(
            "muscles.action.handler",
            lambda: (_ for _ in ()).throw(RuntimeError("boom")),
            **{"muscles.action.name": "bookings.create", "api_key": "secret"},
        )

    record: SpanRecord = tracer.records[0]
    assert record.status == "error"
    assert record.attributes["error.type"] == "RuntimeError"
    assert "api_key" not in record.attributes
