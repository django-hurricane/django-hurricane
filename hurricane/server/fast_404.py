import logging
import re
import threading
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


def _extract_first_segment(pat: Any) -> str:
    pat_str = str(pat).strip("^").lstrip("/")
    segment = pat_str.split("/")[0] if pat_str else ""
    if segment in ("$", "?$", "\\Z"):
        return ""
    return segment


def _matches_root(pat: Any) -> bool:
    return bool(hasattr(pat, "regex") and (pat.regex.match("") or pat.regex.match("/")))


def _is_root_catchall(pat: Any, pat_str: str) -> bool:
    regex_str = pat.regex.pattern if hasattr(pat, "regex") else ""
    return bool(
        pat_str.startswith(("<path:", "<slug:", "<str:"))
        or regex_str.startswith(("^.*", "^.+", "^(?P<"))
        or regex_str in ("^", "^/", "^/?")
    )


def _is_i18n_pattern(pat: Any) -> bool:
    try:
        from django.urls.resolvers import LocalePrefixPattern

        if isinstance(pat, LocalePrefixPattern):
            return True
    except ImportError:
        pass
    cls = getattr(pat, "__class__", None)
    return bool(cls is not None and getattr(cls, "__name__", "") == "LocalePrefixPattern")


def _add_i18n_prefixes(prefixes: Set[str]) -> None:
    from django.conf import settings

    prefixes.add("")
    try:
        for lang_code, _ in getattr(settings, "LANGUAGES", []):
            prefixes.add(lang_code.lower())
            prefixes.add(lang_code.split("-")[0].lower())
    except Exception:
        pass


def _process_resolver(p: Any, first_segment: str, is_i18n: bool, is_root: bool, prefixes: Set[str]) -> bool:
    sub_catchall = False
    if first_segment == "" or is_i18n:
        sub_prefixes, sub_catchall = extract_prefixes(p.url_patterns, is_root=is_root)
        prefixes.update(sub_prefixes)
    if first_segment:
        prefixes.add(first_segment)
    return sub_catchall


def _process_pattern(p: Any, is_root: bool, prefixes: Set[str]) -> bool:
    from django.urls.resolvers import URLPattern, URLResolver

    pat = getattr(p, "pattern", None)
    if not pat:
        return False

    first_segment = _extract_first_segment(pat)
    if _matches_root(pat):
        prefixes.add("")

    is_i18n = _is_i18n_pattern(pat)
    if is_i18n:
        _add_i18n_prefixes(prefixes)

    pat_str = str(pat).strip("^").lstrip("/")
    has_catchall = is_root and _is_root_catchall(pat, pat_str)

    if isinstance(p, URLResolver):
        sub_catchall = _process_resolver(p, first_segment, is_i18n, is_root, prefixes)
        return has_catchall or sub_catchall
    if isinstance(p, URLPattern):
        prefixes.add(first_segment)

    return has_catchall


def extract_prefixes(patterns: Any, is_root: bool = True) -> Tuple[Set[str], bool]:
    """
    Recursively inspect Django URL patterns to extract:
    1. Valid top-level path segments (e.g. {'', 'admin', 'api', 'media'}).
    2. has_root_catchall: True if any root pattern can match arbitrary paths.
    """
    prefixes: Set[str] = set()
    has_root_catchall = False

    for p in patterns:
        if _process_pattern(p, is_root, prefixes):
            has_root_catchall = True

    return prefixes, has_root_catchall


def _get_fallback_404_response() -> Tuple[str, List[Tuple[str, str]], bytes]:
    fallback_body = (
        b"<!doctype html>\n"
        b'<html lang="en">\n'
        b"<head>\n"
        b'  <meta charset="utf-8">\n'
        b"  <title>Page Not Found</title>\n"
        b"  <style>\n"
        b"    body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; margin: 0; padding: 3rem; background: #f8fafc; color: #1e293b; }\n"
        b"    .container { max-width: 600px; margin: 0 auto; background: #ffffff; padding: 2.5rem; border-radius: 8px; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1); }\n"
        b"    h1 { margin-top: 0; color: #0f172a; font-size: 1.75rem; }\n"
        b"    p { line-height: 1.6; color: #475569; }\n"
        b"    a { color: #2563eb; text-decoration: none; font-weight: 500; }\n"
        b"    a:hover { text-decoration: underline; }\n"
        b"  </style>\n"
        b"</head>\n"
        b"<body>\n"
        b'  <div class="container">\n'
        b"    <h1>404 &mdash; Page Not Found</h1>\n"
        b"    <p>The requested resource was not found on this server.</p>\n"
        b'    <p><a href="/">&larr; Return to homepage</a></p>\n'
        b"  </div>\n"
        b"</body>\n"
        b"</html>"
    )
    return (
        "404 Not Found",
        [("Content-Type", "text/html; charset=utf-8"), ("Content-Length", str(len(fallback_body)))],
        fallback_body,
    )


def prerender_404() -> Tuple[str, List[Tuple[str, str]], bytes]:
    """
    Deprecated: Fast-404 uses on-demand caching from the real Django 404 handler on first hit.
    Returns the default fallback 404 response.
    """
    return _get_fallback_404_response()


def _verify_root_route(valid_prefixes: Set[str], urlconf: Any = None) -> None:
    from django.urls import Resolver404, resolve

    for root_cand in ["/", ""]:
        try:
            resolve(root_cand, urlconf=urlconf)
            valid_prefixes.add("")
            break
        except Resolver404:
            pass
        except Exception:
            valid_prefixes.add("")
            break


def _determine_effective_mode(mode: str, has_root_catchall: bool, valid_prefixes_len: int, patterns_len: int) -> str:
    if mode == "auto":
        if has_root_catchall:
            logger.info(
                "Root catch-all pattern detected in urls.py (CMS/dynamic routing). Fast-404 operating in signature-only mode"
            )
            return "signature"
        logger.info(f"Fast-404 active in prefix mode ({valid_prefixes_len} prefixes, {patterns_len} signatures)")
        return "prefix"
    if mode == "signature":
        logger.info(f"Fast-404 active in signature-only mode ({patterns_len} signatures)")
        return "signature"
    if mode == "prefix":
        logger.info(f"Fast-404 forced in prefix mode ({valid_prefixes_len} prefixes)")
        return "prefix"
    logger.info("Fast-404 protection disabled")
    return "off"


class Fast404Engine:
    """
    High-performance early 404 protection engine for Hurricane Gateway.
    Filters malicious scanner probes and invalid path prefixes in microseconds.
    Uses on-demand response caching: on cache miss, requests fall through to Django
    to naturally generate and cache the custom rendered 404 page.
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

        # Verify root route resolution using Django's resolver
        _verify_root_route(self.valid_prefixes, urlconf=urlconf)

        # Determine effective operating mode
        self.effective_mode = _determine_effective_mode(
            self.mode, self.has_root_catchall, len(self.valid_prefixes), len(patterns)
        )

        # On-demand response cache: key -> (status, headers, body)
        self._cache: Dict[str, Tuple[str, List[Tuple[str, str]], bytes]] = {}
        self._cache_lock = threading.Lock()
        self._fallback_response = _get_fallback_404_response()
        self.status, self.headers, self.body = self._fallback_response

    def compute_cache_key_asgi(self, scope: Dict[str, Any]) -> str:
        headers = dict(scope.get("headers", []))
        host = headers.get(b"host", b"localhost").decode("utf-8", errors="replace").split(":")[0].lower()
        path = scope.get("path", "")
        parts = path.strip("/").split("/")
        lang = (
            parts[0].lower() if parts and len(parts[0]) <= 5 and ("-" in parts[0] or len(parts[0]) == 2) else "default"
        )
        scheme = scope.get("scheme", "http")
        return f"{host}:{lang}:{scheme}"

    def compute_cache_key_wsgi(self, environ: Dict[str, Any]) -> str:
        host = str(environ.get("HTTP_HOST", "localhost")).split(":")[0].lower()
        path = str(environ.get("PATH_INFO", ""))
        parts = path.strip("/").split("/")
        lang = (
            parts[0].lower() if parts and len(parts[0]) <= 5 and ("-" in parts[0] or len(parts[0]) == 2) else "default"
        )
        scheme = str(environ.get("wsgi.url_scheme", "http"))
        return f"{host}:{lang}:{scheme}"

    def get_cached(self, key: str) -> Optional[Tuple[str, List[Tuple[str, str]], bytes]]:
        with self._cache_lock:
            return self._cache.get(key)

    def store_response(self, key: str, status: str, headers: List[Tuple[str, str]], body: bytes) -> None:
        with self._cache_lock:
            if len(self._cache) >= 128:
                self._cache.pop(next(iter(self._cache)))
            self._cache[key] = (status, headers, body)
            self.status, self.headers, self.body = status, headers, body

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

    def get_response(self, key: Optional[str] = None) -> Tuple[str, List[Tuple[str, str]], bytes]:
        """Return cached 404 response if available, or fallback HTML response."""
        if key:
            cached = self.get_cached(key)
            if cached is not None:
                return cached
        return self.status, self.headers, self.body
