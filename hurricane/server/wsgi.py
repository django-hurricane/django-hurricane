from typing import Any, Callable, Optional


class HurricaneWSGIContainer:
    """
    Backward-compatible WSGI container wrapping a WSGI application.
    """

    def __init__(
        self,
        handler: Any = None,
        wsgi_application: Optional[Callable] = None,
        executor: Any = None,
        observe: bool = True,
    ) -> None:
        self.handler = handler
        self.wsgi_application = wsgi_application
        self.executor = executor
        self.observe = observe

    def __call__(self, environ_or_request: Any, start_response: Optional[Callable] = None) -> Any:
        if callable(start_response) and callable(self.wsgi_application):
            return self.wsgi_application(environ_or_request, start_response)
        return None
