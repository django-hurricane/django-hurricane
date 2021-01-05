from hurricane.amqp.basehandler import TopicHandler


class MyTestHandler(TopicHandler):
    def on_message(self, _unused_channel, basic_deliver, properties, body):
        print(body.decode("utf-8"))
        self.acknowledge_message(basic_deliver.delivery_tag)
