from __future__ import annotations

from types import SimpleNamespace

import pytest

from muscles import (
    TelemetryProvider,
    collect_package_capabilities,
    doctor_application,
    inspect_application,
    install_package,
    resolve_telemetry,
)

import muscles_otel.package as package_module
from muscles_otel import MusclesTracer, OtelPackage, init_package


def test_otel_package_implements_full_lifecycle_contract():
    package = OtelPackage()

    for hook_name in (
        "build_runtime",
        "services",
        "actions",
        "inspection_provider",
        "doctor_provider",
        "generator_providers",
    ):
        assert callable(getattr(package, hook_name))


def test_otel_package_can_be_installed_directly_through_core_lifecycle():
    app = SimpleNamespace()

    runtime = install_package(app, {"enabled": True}, OtelPackage())

    assert isinstance(runtime, MusclesTracer)
    assert app.container.resolve(TelemetryProvider) is runtime
    assert resolve_telemetry(app) is runtime
    assert inspect_application(app)["packages"] == [{"namespace": "otel", "name": "OtelPackage"}]


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


def test_otel_package_reports_safe_inspect_and_doctor_payloads_from_same_runtime():
    app = SimpleNamespace()
    runtime = init_package(app, {"enabled": True})

    with resolve_telemetry(app).span("project.operation", **{"safe.count": 1}):
        pass

    records_count = len(runtime.records)
    capabilities = collect_package_capabilities(app)
    doctor = doctor_application(app)

    assert capabilities["otel"]["enabled"] is True
    assert capabilities["otel"]["provider"] == "MusclesTracer"
    assert capabilities["otel"]["records.count"] == records_count
    assert capabilities["otel"]["records.count"] >= 1
    assert doctor["packages"]["otel"]["status"] == "ok"


def test_otel_package_applies_project_attributes_to_every_span():
    app = SimpleNamespace()
    runtime = install_package(
        app,
        {
            "enabled": True,
            "service_name": "booking-api",
            "attributes": {
                "deployment.environment": "test",
                "api_key": "must-not-leak",
            },
        },
        OtelPackage(),
    )

    with resolve_telemetry(app).span("project.healthcheck", **{"http.route": "/ready"}):
        pass

    record = runtime.records[-1]
    assert record.name == "project.healthcheck"
    assert record.attributes == {
        "service.name": "booking-api",
        "deployment.environment": "test",
        "http.route": "/ready",
    }


def test_disabled_package_provider_records_no_spans():
    app = SimpleNamespace()
    telemetry = init_package(app, {"enabled": False})

    with telemetry.span("custom.disabled", **{"safe.count": 1}):
        pass

    assert telemetry.records == []


def test_init_package_does_not_swallow_core_lifecycle_errors(monkeypatch):
    app = SimpleNamespace()

    def broken_install_hook(*args, **kwargs):
        raise RuntimeError("install failed")

    monkeypatch.setattr(package_module, "_resolve_install_hook", lambda: broken_install_hook)

    with pytest.raises(RuntimeError, match="install failed"):
        init_package(app, {"enabled": True})
