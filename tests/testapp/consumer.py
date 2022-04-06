from typing import List

from hurricane.amqp.basehandler import TopicHandler


class MyTestHandler(TopicHandler):
    def on_message(self, _unused_channel, basic_deliver, properties, body):
        print(body.decode("utf-8"))
        self.acknowledge_message(basic_deliver.delivery_tag)


class BindTestHandler(MyTestHandler):
    def get_routing_keys(self, queue_name: str) -> List[str]:
        return [queue_name.rsplit(".", 1)[0]]


class IncorrectHandler:
    def __init__(self):
        print("Incorrect Handler")
