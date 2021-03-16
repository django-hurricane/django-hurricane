from hurricane.webhooks.base import Webhook


class StartupWebhook(Webhook):
    code = "startup"

    def __init__(self):
        super(Webhook, self).__init__()
        self.data = {"info": "Startup webhook"}


class LivenessWebhook(Webhook):
    code = "liveness"

    def __init__(self):
        super(Webhook, self).__init__()
        self.data = {"info": "Liveness webhook"}


class ReadinessWebhook(Webhook):
    code = "readiness"

    def __init__(self):
        super(Webhook, self).__init__()
        self.data = {"info": "Readiness webhook"}
