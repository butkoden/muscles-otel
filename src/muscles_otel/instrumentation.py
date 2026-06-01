from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass, field
import inspect
from collections.abc import Iterable
from time import perf_counter
from typing import Any, Iterator


SENSITIVE_ATTRIBUTE_PARTS = ("secret", "token", "password", "payload", "api_key", "authorization")


@dataclass(frozen=True)
class SpanRecord:
    name: str
    duration_ms: float
    attributes: dict[str, Any]
    status: str = "ok"
    events: list[dict[str, Any]] = field(default_factory=list)


class MusclesTracer:
    def __init__(self, enabled: bool = False) -> None:
        self.enabled = enabled
        self.records: list[SpanRecord] = []

    @contextmanager
    def span(self, name: str, **attributes: Any) -> Iterator[None]:
        if not self.enabled:
            yield
            return
        started = perf_counter()
        status = "ok"
        events: list[dict[str, Any]] = []
        safe_attributes = _redact_attributes(attributes)
        try:
            yield
        except Exception as exc:
            status = "error"
            safe_attributes["error.type"] = exc.__class__.__name__
            events.append({"name": "exception", "attributes": {"error.type": exc.__class__.__name__}})
            raise
        finally:
            duration_ms = (perf_counter() - started) * 1000.0
            self.records.append(
                SpanRecord(
                    name=name,
                    duration_ms=duration_ms,
                    attributes=safe_attributes,
                    status=status,
                    events=events,
                )
            )

    def instrument_call(self, span_name: str, callback, **attributes: Any):
        with self.span(span_name, **attributes):
            return callback()

    def find(self, name: str) -> list[SpanRecord]:
        return [record for record in self.records if record.name == name]


class OtelStrategyMixin:
    def execute(self, *args, **kwargs):
        tracer = kwargs.pop("otel_tracer", None)
        container = kwargs.get("container")
        if tracer is None:
            return super().execute(*args, **kwargs)
        return tracer.instrument_call(
            "muscles.strategy.execute",
            lambda: super(OtelStrategyMixin, self).execute(*args, **kwargs),
            **{
                "muscles.app": _app_name(container),
                "muscles.strategy": self.__class__.__name__,
            },
        )


def instrument_server_dispatch(
    tracer: MusclesTracer,
    callback,
    *,
    app_name: str | None = None,
    route_name: str | None = None,
    route_path: str | None = None,
    transport: str | None = None,
):
    return tracer.instrument_call(
        "muscles.server.dispatch",
        callback,
        **{
            "muscles.app": app_name,
            "muscles.route.name": route_name,
            "muscles.route.path": route_path,
            "muscles.transport": transport,
        },
    )


def instrument_action_dispatch(
    tracer: MusclesTracer,
    app,
    *,
    action_name: str,
    payload: dict[str, Any] | None = None,
    transport: str | None = None,
):
    from muscles.core import (
        ActionDispatcher,
        ActionError,
        ActionExecutionError,
        ActionPermissionDenied,
        ActionResult,
    )

    dispatcher = ActionDispatcher(app)
    action = dispatcher.registry.get_action(action_name)
    attributes = _action_attributes(app, action_name, transport)
    if action is None:
        return tracer.instrument_call(
            "muscles.action.execute",
            lambda: dispatcher.execute(action_name, payload or {}, transport=transport),
            **attributes,
        )

    value_holder: dict[str, Any] = {}

    def execute():
        context = _action_context(app, dispatcher.registry, action, transport)
        dispatcher._check_transport(action, transport)
        with tracer.span("muscles.action.validate", **attributes):
            dispatcher._validate(action, payload or {})
        with tracer.span("muscles.action.rules", **attributes):
            dispatcher._check_rules(action, payload or {}, context)
        with tracer.span("muscles.action.handler", **attributes):
            try:
                value = dispatcher._call_handler(action, payload or {}, context)
                if inspect.isawaitable(value):
                    if hasattr(value, "close"):
                        value.close()
                    raise ActionExecutionError(
                        action.name,
                        "Async action handlers are not supported by ActionDispatcher.execute; use an async dispatcher.",
                    )
            except ActionError:
                raise
            except PermissionError as exc:
                raise ActionPermissionDenied(action.name, str(exc)) from exc
            except Exception as exc:
                raise ActionExecutionError(action.name, str(exc)) from exc
        result = ActionResult(
            action_name=action.name,
            value=value,
            transport=transport,
            is_stream=_is_stream_result(value),
        )
        value_holder["result"] = result
        return result

    try:
        result = tracer.instrument_call("muscles.action.execute", execute, **attributes)
    finally:
        result = value_holder.get("result")
        if result is not None and tracer.records:
            execute_span = tracer.records[-1]
            if execute_span.name == "muscles.action.execute":
                execute_span.attributes["muscles.result.type"] = type(result.value).__name__
    return result


def _action_context(app, registry, action, transport):
    from muscles.core import ActionContext

    return ActionContext(application=app, registry=registry, action=action, transport=transport, metadata={})


def _action_attributes(app, action_name: str, transport: str | None) -> dict[str, Any]:
    return {
        "muscles.app": _app_name(app),
        "muscles.action.name": action_name,
        "muscles.transport": transport,
    }


def _app_name(app) -> str | None:
    if app is None:
        return None
    if isinstance(app, str):
        return app
    return app.__class__.__name__


def _redact_attributes(attributes: dict[str, Any]) -> dict[str, Any]:
    safe = {}
    for key, value in attributes.items():
        lowered = key.lower()
        if any(part in lowered for part in SENSITIVE_ATTRIBUTE_PARTS):
            continue
        safe[key] = value
    return safe


def _is_stream_result(value: Any) -> bool:
    if isinstance(value, (str, bytes, dict, list, tuple)):
        return False
    return isinstance(value, Iterable)
