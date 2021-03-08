from hurricane.webhooks.registry import WebhookRegistry
from hurricane.webhooks.webhook_types import LivenessWebhook, StartupWebhook

webhook_registry = WebhookRegistry()
webhook_registry.register(StartupWebhook)
webhook_registry.register(LivenessWebhook)
