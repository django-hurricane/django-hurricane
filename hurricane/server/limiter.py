import logging
import threading
import time
from typing import Any, Dict, List, Optional, Tuple

try:
    import structlog

    logger = structlog.get_logger("hurricane.server.limiter")
except ImportError:
    logger = logging.getLogger("hurricane.server.limiter")


def normalize_proxy_header(header: str) -> str:
    """Normalize header name to WSGI format (e.g. 'X-Forwarded-For' -> 'HTTP_X_FORWARDED_FOR')."""
    clean = header.upper().replace("-", "_")
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

        # 1. Check if explicitly disabled via CLI
        if options.get("no_rate_limit"):
            logger.info("Rate limiter disabled")
            return None

        cli_rate = options.get("rate_limit")
        if cli_rate in ("off", "none", "false", "no", False):
            logger.info("Rate limiter disabled")
            return None

        # 2. Check Django settings
        setting_val = getattr(settings, "HURRICANE_RATE_LIMIT", True)
        if setting_val is False or setting_val in ("off", "none", "false", "no"):
            logger.info("Rate limiter disabled")
            return None

        rate = 10.0
        burst = 30.0
        proxy_header_input = options.get("rate_limit_proxy_header") or "X-Forwarded-For"

        # Parse settings dict if provided
        if isinstance(setting_val, dict):
            if not setting_val.get("ENABLED", True):
                logger.info("Rate limiter disabled")
                return None
            if "RATE" in setting_val:
                rate = float(setting_val["RATE"])
            if "BURST" in setting_val:
                burst = float(setting_val["BURST"])
            if "PROXY_HEADER" in setting_val:
                proxy_header_input = setting_val["PROXY_HEADER"]

        # Parse CLI overrides if provided
        if cli_rate and cli_rate not in ("auto", "on", "true", "yes", True):
            clean_rate = str(cli_rate).lower().removesuffix("/s").removesuffix("/sec")
            try:
                rate = float(clean_rate)
            except ValueError:
                pass

        if options.get("rate_limit_burst") is not None:
            try:
                burst = float(options["rate_limit_burst"])
            except (ValueError, TypeError):
                pass

        proxy_header = normalize_proxy_header(proxy_header_input)
        header_display = proxy_header_input.removeprefix("HTTP_").replace("_", "-")

        return cls(
            rate=rate,
            burst=burst,
            proxy_header=proxy_header,
            header_display=header_display,
        )

    def is_allowed(self, environ: Dict[str, Any]) -> bool:
        """Check if incoming request is allowed under rate limits."""
        client_ip = extract_client_ip(environ, self.proxy_header)
        return self.limiter.allow(client_ip)

    def get_response(self) -> Tuple[str, List[Tuple[str, str]], bytes]:
        """Return 429 response tuple without writing to log files."""
        return self.status, self.headers, self.body
