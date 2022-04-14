class Channel:
    def close(self):
        print("dummy")

    def basic_nack(self, delivery_tag, requeue):
        print("dummy")

    def basic_cancel(self, tag, cb):
        print("dummy")


class Deliver:
    delivery_tag = "Test"


class BasicProperties:
    app_id = "test"
