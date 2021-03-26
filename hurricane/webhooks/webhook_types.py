from hurricane.webhooks.base import Webhook


class StartupWebhook(Webhook):
    code = "startup"

    def __init__(self):
        super(Webhook, self).__init__()
        self.data = {"info": "Startup webhook", "type": self.code}


class LivenessWebhook(Webhook):
    code = "liveness"

    def __init__(self):
        super(Webhook, self).__init__()
        self.data = {"info": "Liveness webhook", "type": self.code}


class ReadinessWebhook(Webhook):
    code = "readiness"

    def __init__(self):
        super(Webhook, self).__init__()
        self.data = {"info": "Readiness webhook", "type": self.code}
