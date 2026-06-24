import anyio

from app.middleware import logging as logging_module


class FakeURL:
    path = "/api/v1/estimate"


class FakeRequest:
    method = "POST"
    url = FakeURL()


class FakeResponse:
    status_code = 200


class FakeBoundLogger:
    def __init__(self):
        self.bound = None
        self.events = []

    def bind(self, **kwargs):
        self.bound = kwargs
        return self

    def info(self, event, **kwargs):
        self.events.append((event, kwargs))


async def fake_call_next(request):
    return FakeResponse()


def test_logging_middleware_emits_structured_request_log(monkeypatch):
    fake_logger = FakeBoundLogger()

    monkeypatch.setattr(logging_module, "structured_logger", fake_logger)

    response = anyio.run(logging_module.logging_middleware, FakeRequest(), fake_call_next)

    assert response.status_code == 200
    assert fake_logger.bound["endpoint"] == "/api/v1/estimate"
    assert isinstance(fake_logger.bound["request_id"], str)
    assert len(fake_logger.bound["request_id"]) > 8

    assert fake_logger.events
    event, fields = fake_logger.events[0]

    assert event == "http_request_completed"
    assert fields["method"] == "POST"
    assert fields["status_code"] == 200
    assert isinstance(fields["latency_ms"], int)
    assert fields["latency_ms"] >= 0
