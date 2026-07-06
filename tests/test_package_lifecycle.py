from __future__ import annotations

from types import SimpleNamespace

from muscles import TelemetryProvider, collect_package_capabilities, doctor_application

from muscles_otel import MusclesTracer, init_package


def test_otel_package_registers_telemetry_provider_through_lifecycle():
    app = SimpleNamespace()

    runtime = init_package(app, {"enabled": True})

    assert isinstance(runtime, MusclesTracer)
    telemetry = app.container.resolve(TelemetryProvider)
    assert telemetry is runtime

    with telemetry.span("custom.span", **{"query": "raw question", "safe.count": 1}):
        pass

    assert telemetry.records[-1].name == "custom.span"
    assert telemetry.records[-1].attributes == {"safe.count": 1}


def test_otel_package_reports_safe_inspect_and_doctor_payloads():
    app = SimpleNamespace()
    init_package(app, {"enabled": True})

    capabilities = collect_package_capabilities(app)
    doctor = doctor_application(app)

    assert capabilities["otel"]["enabled"] is True
    assert capabilities["otel"]["provider"] == "MusclesTracer"
    assert doctor["packages"]["otel"]["status"] == "ok"


def test_disabled_package_provider_records_no_spans():
    app = SimpleNamespace()
    telemetry = init_package(app, {"enabled": False})

    with telemetry.span("custom.disabled", **{"safe.count": 1}):
        pass

    assert telemetry.records == []
