import logging
import re
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

try:
    import structlog

    logger = structlog.get_logger("hurricane.server.fast_404")
except ImportError:
    logger = logging.getLogger("hurricane.server.fast_404")

DEFAULT_ANTI_DJANGO_PATTERNS: List[str] = [
    # 1. Non-Python Executable / Script Extensions
    r"\.php[0-9]?$",
    r"\.asp[x]?$",
    r"\.jsp[x]?$",
    r"\.cgi$",
    r"\.pl$",
    r"\.action$",
    r"\.do$",
    # 2. Sensitive Config & Environment Files
    r"^/\.env(\..*)?$",
    r"^/\.git(/.*)?$",
    r"^/\.svn(/.*)?$",
    r"^/\.hg(/.*)?$",
    r"^/\.DS_Store$",
    r"^/\.aws(/.*)?$",
    r"^/\.docker(/.*)?$",
    r"^/web\.config$",
    r"^/docker-compose\.ya?ml$",
    # 3. Common PHP/CMS Scanner Probes
    r"^/wp-",
    r"^/wordpress",
    r"^/xmlrpc\.php",
    r"^/phpmyadmin",
    r"^/pma",
    r"^/myadmin",
    r"^/admin\.php",
    r"^/login\.php",
    r"^/eval-stdin\.php",
    # 4. Dangerous Tools & Remote Code Execution Probes
    r"^/cgi-bin/",
    r"^/actuator(/.*)?$",
    r"^/solr(/.*)?$",
    r"^/vendor/phpunit/",
    r"^/autodiscover/",
    r"^/geoserver/",
]


def extract_prefixes(patterns: Any, is_root: bool = True) -> Tuple[Set[str], bool]:
    """
    Recursively inspect Django URL patterns to extract:
    1. Valid top-level path segments (e.g. {'', 'admin', 'api', 'media'}).
    2. has_root_catchall: True if any root pattern can match arbitrary paths.
    """
    from django.urls.resolvers import URLPattern, URLResolver

    prefixes: Set[str] = set()
    has_root_catchall = False

    for p in patterns:
        pat = getattr(p, "pattern", None)
        if not pat:
            continue

        pat_str = str(pat).strip("^").lstrip("/")
        first_segment = pat_str.split("/")[0] if pat_str else ""

        if is_root:
            regex_str = pat.regex.pattern if hasattr(pat, "regex") else ""
            if pat_str.startswith(("<path:", "<slug:", "<str:")) or regex_str.startswith(("^.*", "^.+", "^(?P<")):
                has_root_catchall = True

        if isinstance(p, URLResolver):
            if first_segment == "":
                sub_prefixes, sub_catchall = extract_prefixes(p.url_patterns, is_root=is_root)
                prefixes.update(sub_prefixes)
                if sub_catchall:
                    has_root_catchall = True
            else:
                prefixes.add(first_segment)
        elif isinstance(p, URLPattern):
            prefixes.add(first_segment)

    return prefixes, has_root_catchall


def prerender_404(urlconf: Any = None) -> Tuple[str, List[Tuple[str, str]], bytes]:
    """
    Pre-renders Django's configured 404 handler with a synthetic request traversing
    the configured middleware stack so that request attributes (e.g. request.user,
    request.session, and custom middleware attributes) are properly populated.
    Falls back gracefully to standard HTML if rendering fails.
    """
    from django.conf import settings
    from django.core.exceptions import MiddlewareNotUsed
    from django.core.handlers.exception import convert_exception_to_response
    from django.test import RequestFactory
    from django.urls import get_resolver
    from django.utils.module_loading import import_string
    from django.views.defaults import page_not_found

    try:
        resolver = get_resolver(urlconf)
        handler = getattr(resolver.urlconf_module, "handler404", page_not_found)
        if isinstance(handler, str):
            handler = import_string(handler)

        handler_callable: Callable[..., Any] = handler

        def _invoke_view(request: Any) -> Any:
            try:
                response = handler_callable(request, exception=Exception("Page not found"))
            except TypeError:
                response = handler_callable(request)

            if hasattr(response, "render") and callable(response.render):
                response = response.render()
            return response

        # Construct middleware chain with the 404 handler at the core
        chain = convert_exception_to_response(_invoke_view)
        middleware_list = getattr(settings, "MIDDLEWARE", None)
        if middleware_list is None:
            middleware_list = getattr(settings, "MIDDLEWARE_CLASSES", [])

        for mw_path in reversed(middleware_list):
            try:
                mw_class = import_string(mw_path)
                try:
                    mw_instance = mw_class(chain)
                except TypeError:
                    # Support old-style middleware without get_response in constructor
                    mw_instance = mw_class()
                    if hasattr(mw_instance, "process_request"):
                        _prev_chain = chain

                        def _wrapped(req, _inst=mw_instance, _nxt=_prev_chain):
                            res = _inst.process_request(req)
                            if res:
                                return res
                            res = _nxt(req)
                            if hasattr(_inst, "process_response"):
                                res = _inst.process_response(req, res)
                            return res

                        chain = convert_exception_to_response(_wrapped)
                        continue
            except MiddlewareNotUsed:
                continue
            except Exception as mw_err:
                logger.debug(f"Fast-404: Skipping middleware {mw_path} during prerender: {mw_err}")
                continue

            if mw_instance is not None:
                chain = convert_exception_to_response(mw_instance)

        rf = RequestFactory()
        req = rf.get("/__hurricane_fast_404_bootstrap__")

        # Defensive fallbacks for user and session in case middleware is missing/omitted
        if not hasattr(req, "user"):
            try:
                from django.contrib.auth.models import AnonymousUser

                req.user = AnonymousUser()
            except Exception:
                pass
        if not hasattr(req, "session"):
            try:
                from django.contrib.sessions.backends.base import SessionBase

                req.session = SessionBase()
            except Exception:
                pass

        resp: Any = chain(req)
        if hasattr(resp, "render") and callable(resp.render):
            resp = resp.render()

        status_code = getattr(resp, "status_code", 404)
        status_line = f"{status_code} Not Found" if status_code == 404 else f"{status_code} OK"
        headers = [(k, v) for k, v in resp.items()] if hasattr(resp, "items") else []
        body = getattr(resp, "content", b"")
        return status_line, headers, body
    except Exception as e:
        logger.warning(f"Fast-404 pre-render fallback used ({e})")
        fallback_body = (
            b'<!doctype html>\n<html lang="en">\n<head><title>Not Found</title></head>\n'
            b"<body><h1>Not Found</h1><p>The requested resource was not found on this server.</p></body>\n</html>"
        )
        return (
            "404 Not Found",
            [("Content-Type", "text/html; charset=utf-8"), ("Content-Length", str(len(fallback_body)))],
            fallback_body,
        )


class Fast404Engine:
    """
    High-performance early 404 protection engine for Hurricane Gateway.
    Filters malicious scanner probes and invalid path prefixes in microseconds.
    """

    def __init__(
        self,
        mode: str = "auto",
        extra_patterns: Optional[List[str]] = None,
        extra_prefixes: Optional[Set[str]] = None,
        urlconf: Any = None,
    ):
        from django.conf import settings
        from django.urls import get_resolver

        self.mode = mode.lower()
        patterns = list(DEFAULT_ANTI_DJANGO_PATTERNS)
        if extra_patterns:
            patterns.extend(extra_patterns)
        self.signature_regex = re.compile("|".join(f"(?:{p})" for p in patterns))

        # Introspect urlpatterns
        resolver = get_resolver(urlconf)
        self.valid_prefixes, self.has_root_catchall = extract_prefixes(resolver.url_patterns, is_root=True)

        # Include standard prefixes (media, static, extra)
        if hasattr(settings, "STATIC_URL") and settings.STATIC_URL:
            self.valid_prefixes.add(settings.STATIC_URL.strip("/"))
        if hasattr(settings, "MEDIA_URL") and settings.MEDIA_URL:
            self.valid_prefixes.add(settings.MEDIA_URL.strip("/"))
        if extra_prefixes:
            self.valid_prefixes.update(extra_prefixes)

        # Determine effective operating mode
        if self.mode == "auto":
            if self.has_root_catchall:
                self.effective_mode = "signature"
                logger.info(
                    "Root catch-all pattern detected in urls.py (CMS/dynamic routing). Fast-404 operating in signature-only mode"
                )
            else:
                self.effective_mode = "prefix"
                logger.info(
                    f"Fast-404 active in prefix mode ({len(self.valid_prefixes)} prefixes, {len(patterns)} signatures)"
                )
        elif self.mode == "signature":
            self.effective_mode = "signature"
            logger.info(f"Fast-404 active in signature-only mode ({len(patterns)} signatures)")
        elif self.mode == "prefix":
            self.effective_mode = "prefix"
            logger.info(f"Fast-404 forced in prefix mode ({len(self.valid_prefixes)} prefixes)")
        else:
            self.effective_mode = "off"
            logger.info("Fast-404 protection disabled")

        # Pre-render 404 error response
        self.status, self.headers, self.body = prerender_404(urlconf)

    @classmethod
    def from_options(cls, options: Dict[str, Any]) -> Optional["Fast404Engine"]:
        """Factory creating engine from command options and Django settings."""
        from django.conf import settings

        # Check if explicitly disabled via CLI
        if options.get("no_fast_404"):
            return None

        # Check Django settings
        setting_val = getattr(settings, "HURRICANE_FAST_404", getattr(settings, "FAST_404", "auto"))
        if setting_val is False or setting_val == "off":
            return None

        # Determine strategy from CLI or settings
        cli_mode = options.get("fast_404")
        if cli_mode and cli_mode != "auto":
            mode = cli_mode
        elif setting_val and setting_val != "auto":
            mode = setting_val
        else:
            mode = "auto"

        if mode in (False, "off"):
            return None

        extra_patterns = getattr(settings, "HURRICANE_FAST_404_PATTERNS", getattr(settings, "FAST_404_PATTERNS", None))
        extra_prefixes = getattr(
            settings, "HURRICANE_FAST_404_EXTRA_PREFIXES", getattr(settings, "FAST_404_EXTRA_PREFIXES", None)
        )
        if extra_prefixes:
            extra_prefixes = set(extra_prefixes)

        return cls(
            mode=str(mode),
            extra_patterns=extra_patterns,
            extra_prefixes=extra_prefixes,
        )

    def should_drop(self, path: str) -> Optional[Tuple[str, str]]:
        """
        Evaluate if path should be dropped with early 404.
        Returns (reason_type, detail) if dropped, None if allowed.
        """
        if self.effective_mode == "off":
            return None

        # 1. Anti-Django Signature Match
        if self.signature_regex.search(path):
            return "signature", path

        # 2. Prefix Whitelist Match (when in prefix mode)
        if self.effective_mode == "prefix":
            # Extract first path segment (e.g. "/api/v1" -> "api", "/" -> "")
            clean_path = path.split("?")[0].lstrip("/")
            first_segment = clean_path.split("/")[0] if clean_path else ""
            if first_segment not in self.valid_prefixes:
                return "prefix", first_segment

        return None

    def log_drop(self, environ: Dict[str, Any], path: str, reason_type: str, detail: str) -> None:
        """Emit structured log for fast-dropped request."""
        remote_addr = environ.get("REMOTE_ADDR", "-")
        method = environ.get("REQUEST_METHOD", "GET")
        logger.warning(f"Fast-404: Dropped {remote_addr} {method} {path} ({reason_type} match: {detail})")

    def get_response(self) -> Tuple[str, List[Tuple[str, str]], bytes]:
        """Return pre-rendered 404 response tuple (status_line, headers, body_bytes)."""
        return self.status, self.headers, self.body
