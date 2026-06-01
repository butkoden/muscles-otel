from muscles_otel import MusclesTracer


def test_disabled_tracer_has_no_records():
    tracer = MusclesTracer(enabled=False)
    value = tracer.instrument_call("muscles.action", lambda: 42, action="bookings.create")
    assert value == 42
    assert tracer.records == []


def test_enabled_tracer_records_span():
    tracer = MusclesTracer(enabled=True)
    tracer.instrument_call("muscles.action", lambda: "ok", action="bookings.create")
    assert len(tracer.records) == 1
    record = tracer.records[0]
    assert record.name == "muscles.action"
    assert record.attributes["action"] == "bookings.create"
    assert record.duration_ms >= 0
