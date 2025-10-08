class Channel:
    def close(self):
        pass

    def basic_nack(self, delivery_tag, requeue):
        pass

    def basic_cancel(self, tag, cb):
        pass


class IOLoop:
    def stop(self):
        pass


class Connection:
    ioloop = IOLoop()


class Deliver:
    delivery_tag = "Test"


class BasicProperties:
    app_id = "test"


def simple_error_function():
    raise Exception("Test")


def _get_wsgi_container():
    import sys
    from unittest.mock import patch

    if "hurricane.server.wsgi" in sys.modules:
        from hurricane.server.wsgi import HurricaneWSGIContainer

        return HurricaneWSGIContainer

    with patch("importlib.metadata.version", return_value="0.0"):
        from hurricane.server.wsgi import HurricaneWSGIContainer

    return HurricaneWSGIContainer


def test_sanitize_header_value_strips_leading_whitespace():
    HurricaneWSGIContainer = _get_wsgi_container()

    value = ' sessionid=""; expires=Thu, 01 Jan 1970 00:00:00 GMT; Max-Age=0; Path=/; SameSite=Lax'
    assert (
        HurricaneWSGIContainer._sanitize_header_value(value)
        == 'sessionid=""; expires=Thu, 01 Jan 1970 00:00:00 GMT; Max-Age=0; Path=/; SameSite=Lax'
    )


def test_sanitize_header_value_drops_empty_values():
    HurricaneWSGIContainer = _get_wsgi_container()
    assert HurricaneWSGIContainer._sanitize_header_value("   ") is None
