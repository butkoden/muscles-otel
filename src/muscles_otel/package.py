from __future__ import annotations

import inspect
from collections.abc import Mapping
from typing import Any

from .instrumentation import MusclesTracer


class OtelPackage:
    namespace = "otel"

    def build_runtime(self, app, config: Mapping[str, Any]):
        del app
        package_config = _normalize_config(config)
        return MusclesTracer(enabled=_as_bool(package_config.get("enabled", False)))

    def services(self, app, runtime: MusclesTracer, config: Mapping[str, Any] | None = None):
        del app, config
        services = [_package_service(MusclesTracer, lambda: runtime)]
        telemetry_type = _telemetry_provider_type()
        if telemetry_type is not None:
            services.append(_package_service(telemetry_type, lambda: runtime))
        return services

    def actions(self, app, runtime: MusclesTracer, config: Mapping[str, Any] | None = None):
        del app, runtime, config
        return []

    def inspection_provider(self, app, runtime: MusclesTracer, config: Mapping[str, Any] | None = None):
        del app, config

        def inspect_otel() -> dict[str, Any]:
            return {
                "provider": "MusclesTracer",
                "enabled": runtime.enabled,
                "records.count": len(runtime.records),
            }

        return inspect_otel

    def doctor_provider(self, app, runtime: MusclesTracer, config: Mapping[str, Any] | None = None):
        del app, config

        def doctor_otel() -> dict[str, Any]:
            return {
                "status": "ok",
                "checks": [
                    {
                        "name": "otel.telemetry_provider",
                        "status": "ok",
                        "enabled": runtime.enabled,
                    }
                ],
            }

        return doctor_otel

    def generator_providers(self, app, runtime: MusclesTracer, config: Mapping[str, Any] | None = None):
        del app, runtime, config
        return []


def init_package(app, config: Mapping[str, Any] | None = None):
    package = OtelPackage()
    installable = _resolve_install_hook()
    if installable is not None:
        return installable(app=app, config=config, package=package)  # type: ignore[call-arg]

    package_config = _normalize_config(config or {})
    runtime = package.build_runtime(app, package_config)
    _apply_services(app, package.services(app, runtime, config=package_config))
    return runtime


def _normalize_config(config: Any) -> dict[str, Any]:
    if config is None:
        return {}
    if isinstance(config, Mapping):
        return dict(config)
    if hasattr(config, "_object"):
        return _normalize_config(getattr(config, "_object"))
    if hasattr(config, "__dict__"):
        return dict(getattr(config, "__dict__") or {})
    try:
        return dict(config)
    except Exception:
        return {}


def _as_bool(value: Any) -> bool:
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on", "enabled"}
    return bool(value)


def _resolve_install_hook():
    try:
        from muscles.core.lifecycle import install_package  # type: ignore[import-not-found]

        return install_package
    except Exception:
        pass
    try:
        from muscles.lifecycle import install_package  # type: ignore[import-not-found]

        return install_package
    except Exception:
        return None


def _package_service(interface: type, provider: Any):
    try:
        from muscles import PackageService  # type: ignore[import-not-found]

        return PackageService(interface=interface, provider=provider)
    except Exception:
        return {"interface": interface, "provider": provider}


def _telemetry_provider_type():
    try:
        from muscles import TelemetryProvider  # type: ignore[import-not-found]

        return TelemetryProvider
    except Exception:
        return None


def _apply_services(app, services: Any) -> None:
    container = _ensure_container(app)
    for service in services or []:
        if isinstance(service, Mapping):
            container.register(
                service["interface"],
                service["provider"],
                *tuple(service.get("args", ())),
                scope=service.get("scope", getattr(container, "APP", "app")),
                **dict(service.get("kwargs", {})),
            )
            continue
        container.register(
            service.interface,
            service.provider,
            *tuple(getattr(service, "args", ())),
            scope=getattr(service, "scope", getattr(container, "APP", "app")),
            **dict(getattr(service, "kwargs", {})),
        )


def _ensure_container(app):
    container = getattr(app, "container", None)
    if container is None:
        container = _dependency_container()
        setattr(app, "container", container)
    return container


def _dependency_container():
    try:
        from muscles import DependencyContainer  # type: ignore[import-not-found]

        return DependencyContainer()
    except Exception:  # pragma: no cover
        return _LegacyContainer()


class _LegacyContainer:
    def __init__(self):
        self._entries: dict[type, tuple[Any, tuple[Any, ...], dict[str, Any]]] = {}

    def register(self, interface: type, provider: Any, *args: Any, **kwargs: Any):
        kwargs.pop("scope", None)
        self._entries[interface] = (provider, args, kwargs)

    def resolve(self, interface: type):
        if interface not in self._entries:
            raise KeyError(f"Dependency {interface.__name__} not registered")
        provider, args, kwargs = self._entries[interface]
        if inspect.isclass(provider):
            return provider(*args, **kwargs)
        if callable(provider):
            return provider(*args, **kwargs)
        return provider
