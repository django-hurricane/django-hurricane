from hurricane.webhooks.exceptions import WebhookCodeAlreadyRegistered


class WebhookRegistry:

    """
    Registering webhooks and storing them in a webhooks dictionary.
    """

    def __init__(self):
        self.webhooks = {}

    def register(self, webhook_cls):
        if webhook_cls.code in self.webhooks:
            raise WebhookCodeAlreadyRegistered(f"Webhook Code ({webhook_cls.code}) is already registered.")
        self.webhooks[webhook_cls.code] = webhook_cls()

    def unregister(self, webhook_cls):
        try:
            del self.webhooks[webhook_cls.code]
        except KeyError:
            # TODO warn about trying to unregister not registered metric
            pass

    def get(self, code):
        return self.webhooks[code]
