import logging
import threading
import time
from typing import Any, Dict, List, Optional, Tuple

try:
    import structlog

    logger = structlog.get_logger("hurricane.server.limiter")
except ImportError:
    logger = logging.getLogger("hurricane.server.limiter")


def extract_client_ip_asgi(scope: Dict[str, Any], proxy_header_raw: str = "HTTP_X_FORWARDED_FOR") -> str:
    """
    Extract the real client IP address from ASGI scope headers.
    """
    # Convert HTTP_X_FORWARDED_FOR to x-forwarded-for bytes
    header_name = proxy_header_raw.lower()
    if header_name.startswith("http_"):
        header_name = header_name[5:]
    header_name = header_name.replace("_", "-").encode("utf-8")

    headers = dict(scope.get("headers", []))

    # 1. Configured primary proxy header
    if header_name in headers and headers[header_name]:
        raw = headers[header_name].decode("utf-8")
        client = raw.split(",")[0].strip()
        if client:
            return client

    # 2. X-Real-IP fallback
    if b"x-real-ip" in headers and headers[b"x-real-ip"]:
        client = headers[b"x-real-ip"].decode("utf-8").strip()
        if client:
            return client

    # 3. Socket remote addr fallback
    client_info = scope.get("client")
    if client_info and len(client_info) > 0 and client_info[0]:
        return str(client_info[0]).strip()

    return "unknown"


def normalize_proxy_header(header_name: str) -> str:
    """Normalize header name to WSGI format (e.g. 'X-Forwarded-For' -> 'HTTP_X_FORWARDED_FOR')."""
    clean = header_name.upper().replace("-", "_")
    if not clean.startswith("HTTP_") and clean != "REMOTE_ADDR":
        clean = f"HTTP_{clean}"
    return clean


def extract_client_ip(environ: Dict[str, Any], proxy_header: str = "HTTP_X_FORWARDED_FOR") -> str:
    """
    Extract the real client IP address from proxy forwarding headers.
    Takes the leftmost client IP from X-Forwarded-For to bypass intermediate proxies.
    """
    # 1. Configured primary proxy header
    if proxy_header in environ and environ[proxy_header]:
        raw = str(environ[proxy_header])
        client = raw.split(",")[0].strip()
        if client:
            return client

    # 2. X-Real-IP fallback
    if "HTTP_X_REAL_IP" in environ and environ["HTTP_X_REAL_IP"]:
        client = str(environ["HTTP_X_REAL_IP"]).strip()
        if client:
            return client

    # 3. Socket remote addr fallback
    if "REMOTE_ADDR" in environ and environ["REMOTE_ADDR"]:
        return str(environ["REMOTE_ADDR"]).strip()

    return "unknown"


class TokenBucketLimiter:
    """
    Thread-safe in-memory token bucket rate limiter with automatic stale IP pruning.
    """

    def __init__(self, rate: float = 10.0, burst: float = 30.0, max_tracked_ips: int = 50_000):
        self.rate = float(rate)
        self.burst = float(burst)
        self.max_tracked_ips = max_tracked_ips
        self._buckets: Dict[str, Tuple[float, float]] = {}
        self._lock = threading.Lock()

    def allow(self, ip: str) -> bool:
        now = time.monotonic()
        with self._lock:
            if len(self._buckets) >= self.max_tracked_ips:
                self._prune(now)

            tokens, last_time = self._buckets.get(ip, (self.burst, now))
            elapsed = max(0.0, now - last_time)
            tokens = min(self.burst, tokens + elapsed * self.rate)

            if tokens >= 1.0:
                self._buckets[ip] = (tokens - 1.0, now)
                return True
            else:
                self._buckets[ip] = (tokens, now)
                return False

    def _prune(self, now: float, ttl: float = 60.0):
        """Prune inactive or full buckets to bound memory usage."""
        to_delete = [
            ip for ip, (tokens, last_time) in self._buckets.items() if now - last_time > ttl or tokens >= self.burst
        ]
        for ip in to_delete:
            del self._buckets[ip]

        # If still over limit, evict the oldest half
        if len(self._buckets) >= self.max_tracked_ips:
            sorted_items = sorted(self._buckets.items(), key=lambda item: item[1][1])
            for ip, _ in sorted_items[: self.max_tracked_ips // 2]:
                del self._buckets[ip]


DISABLED_RATE_VALUES = ("off", "none", "false", "no", False)


def _is_rate_limiter_disabled(options: Dict[str, Any], settings: Any) -> bool:
    if options.get("no_rate_limit") or options.get("rate_limit") in DISABLED_RATE_VALUES:
        return True

    enabled_setting = getattr(settings, "HURRICANE_RATE_LIMIT_ENABLED", getattr(settings, "RATE_LIMIT_ENABLED", None))
    if enabled_setting is False:
        return True

    setting_val = getattr(settings, "HURRICANE_RATE_LIMIT", getattr(settings, "RATE_LIMIT", True))
    if setting_val is False or setting_val in DISABLED_RATE_VALUES:
        return True

    if isinstance(setting_val, dict) and not setting_val.get("ENABLED", True):
        return True

    return False


def _parse_rate_value(val: Any) -> Optional[float]:
    if val is None or val in (True, "auto", "on", "true", "yes"):
        return None
    clean = str(val).lower().removesuffix("/s").removesuffix("/sec")
    try:
        return float(clean)
    except ValueError:
        return None


def _resolve_settings_config(settings: Any) -> Tuple[float, float, str, bool, bool]:
    rate = 10.0
    burst = 30.0
    proxy_header = "X-Forwarded-For"
    has_burst = False
    has_header = False

    ind_burst = getattr(settings, "HURRICANE_RATE_LIMIT_BURST", getattr(settings, "RATE_LIMIT_BURST", None))
    if ind_burst is not None:
        try:
            burst = float(ind_burst)
            has_burst = True
        except (ValueError, TypeError):
            pass

    ind_header = getattr(
        settings, "HURRICANE_RATE_LIMIT_PROXY_HEADER", getattr(settings, "RATE_LIMIT_PROXY_HEADER", None)
    )
    if ind_header is not None:
        proxy_header = str(ind_header)
        has_header = True

    setting_val = getattr(settings, "HURRICANE_RATE_LIMIT", getattr(settings, "RATE_LIMIT", True))
    if isinstance(setting_val, dict):
        if "RATE" in setting_val:
            parsed_rate = _parse_rate_value(setting_val["RATE"])
            if parsed_rate is not None:
                rate = parsed_rate
        if "BURST" in setting_val:
            try:
                burst = float(setting_val["BURST"])
                has_burst = True
            except (ValueError, TypeError):
                pass
        if "PROXY_HEADER" in setting_val:
            proxy_header = str(setting_val["PROXY_HEADER"])
            has_header = True
    else:
        parsed_rate = _parse_rate_value(setting_val)
        if parsed_rate is not None:
            rate = parsed_rate

    return rate, burst, proxy_header, has_burst, has_header


def _apply_cli_overrides(
    options: Dict[str, Any],
    rate: float,
    burst: float,
    proxy_header: str,
    has_settings_burst: bool,
    has_settings_header: bool,
) -> Tuple[float, float, str]:
    cli_rate = options.get("rate_limit")
    if cli_rate and cli_rate != "10/s":
        parsed = _parse_rate_value(cli_rate)
        if parsed is not None:
            rate = parsed

    cli_burst = options.get("rate_limit_burst")
    if cli_burst is not None and (cli_burst != 30 or not has_settings_burst):
        try:
            burst = float(cli_burst)
        except (ValueError, TypeError):
            pass

    cli_header = options.get("rate_limit_proxy_header")
    if cli_header is not None and (cli_header != "X-Forwarded-For" or not has_settings_header):
        proxy_header = cli_header

    return rate, burst, proxy_header


class RateLimiterEngine:
    """
    High-performance request rate limiter for Hurricane Gateway.
    Protects Django from DoS and flood attacks silently without log bloat.
    """

    def __init__(
        self,
        rate: float = 10.0,
        burst: float = 30.0,
        proxy_header: str = "HTTP_X_FORWARDED_FOR",
        header_display: str = "X-Forwarded-For",
    ):
        self.rate = rate
        self.burst = burst
        self.proxy_header = proxy_header
        self.header_display = header_display
        self.limiter = TokenBucketLimiter(rate=rate, burst=burst)

        # 429 response payload (immutable bytes)
        self.status = "429 Too Many Requests"
        self.body = b"Too Many Requests\n"
        self.headers: List[Tuple[str, str]] = [
            ("Content-Type", "text/plain; charset=utf-8"),
            ("Retry-After", "1"),
            ("Content-Length", str(len(self.body))),
        ]

        logger.info(
            f"Rate limiter active: {self.rate:.1f} req/s (burst: {int(self.burst)}) [IP Header: {header_display}]"
        )

    @classmethod
    def from_options(cls, options: Dict[str, Any]) -> Optional["RateLimiterEngine"]:
        """Factory creating RateLimiterEngine from CLI options and Django settings."""
        from django.conf import settings

        if _is_rate_limiter_disabled(options, settings):
            logger.info("Rate limiter disabled")
            return None

        rate, burst, proxy_header, has_burst, has_header = _resolve_settings_config(settings)
        rate, burst, proxy_header = _apply_cli_overrides(options, rate, burst, proxy_header, has_burst, has_header)

        proxy_header_normalized = normalize_proxy_header(proxy_header)
        header_display = proxy_header.removeprefix("HTTP_").replace("_", "-")

        return cls(
            rate=rate,
            burst=burst,
            proxy_header=proxy_header_normalized,
            header_display=header_display,
        )

    def is_allowed(self, environ: Dict[str, Any]) -> bool:
        """Check if incoming request is allowed under rate limits."""
        client_ip = extract_client_ip(environ, self.proxy_header)
        return self.limiter.allow(client_ip)

    def is_allowed_asgi(self, scope: Dict[str, Any]) -> bool:
        """Check if incoming ASGI request is allowed under rate limits."""
        client_ip = extract_client_ip_asgi(scope, self.proxy_header)
        return self.limiter.allow(client_ip)

    def get_response(self) -> Tuple[str, List[Tuple[str, str]], bytes]:
        """Return 429 response tuple without writing to log files."""
        return self.status, self.headers, self.body
