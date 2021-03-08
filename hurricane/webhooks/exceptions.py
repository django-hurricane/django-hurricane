class WebhookCodeAlreadyRegistered(Exception):

    """
    Exception class for the case, that metric was already registered and should not be registered twice.
    """

    def __init__(self, message):
        raise Exception(message)
