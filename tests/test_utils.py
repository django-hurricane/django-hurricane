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
