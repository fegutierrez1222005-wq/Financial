"""Request context, security headers and rate limiting middleware."""

from __future__ import annotations

import time
import uuid
from collections import defaultdict, deque
from dataclasses import dataclass

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import JSONResponse

from finagent_api.settings import Settings, get_settings
from finagent_core.errors import ErrorCode
from finagent_core.logging import bind_context, get_logger, log_context

logger = get_logger(__name__)

REQUEST_ID_HEADER = "X-Request-ID"


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Assigns a request id, binds log context and records request timing."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        request_id = request.headers.get(REQUEST_ID_HEADER) or f"req_{uuid.uuid4().hex[:16]}"
        request.state.request_id = request_id
        started = time.perf_counter()

        with log_context(request_id=request_id, path=request.url.path, method=request.method):
            bind_context(request_id=request_id)
            try:
                response = await call_next(request)
            except Exception:
                logger.exception(
                    "request_exception",
                    extra={"duration_ms": int((time.perf_counter() - started) * 1000)},
                )
                raise
            duration_ms = int((time.perf_counter() - started) * 1000)
            response.headers[REQUEST_ID_HEADER] = request_id
            response.headers["X-Response-Time-Ms"] = str(duration_ms)
            if not request.url.path.endswith(("/health", "/readiness", "/metrics")):
                logger.info(
                    "request_completed",
                    extra={"status_code": response.status_code, "duration_ms": duration_ms},
                )
            return response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        response.headers.setdefault("Cache-Control", "no-store")
        if get_settings().is_production:
            response.headers.setdefault(
                "Strict-Transport-Security", "max-age=31536000; includeSubDomains"
            )
        return response


@dataclass
class Bucket:
    limit: int
    window_seconds: int = 60


class RateLimiter:
    """Fixed-window counter with a Redis backend and an in-process fallback.

    The in-process backend is correct for a single worker and is used in development and
    tests; Redis is required for a multi-worker deployment and is selected automatically
    when it is reachable.
    """

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._local: dict[str, deque[float]] = defaultdict(deque)
        self._redis = None
        if settings.job_backend == "celery" or settings.environment in ("staging", "production"):
            self._redis = self._connect_redis(settings.redis_url)

    def _connect_redis(self, url: str):  # pragma: no cover - requires a live Redis
        try:
            import redis

            client = redis.Redis.from_url(url, socket_connect_timeout=1)
            client.ping()
            logger.info("rate_limiter_backend", extra={"backend": "redis"})
            return client
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "rate_limiter_redis_unavailable",
                extra={"detail": str(exc)[:160], "fallback": "in_process"},
            )
            return None

    @property
    def backend(self) -> str:
        return "redis" if self._redis is not None else "in_process"

    def check(self, key: str, bucket: Bucket) -> tuple[bool, int]:
        """Return ``(allowed, remaining)``."""
        if not self.settings.rate_limit_enabled:
            return True, bucket.limit
        if self._redis is not None:  # pragma: no cover - requires a live Redis
            try:
                window = int(time.time() // bucket.window_seconds)
                redis_key = f"rl:{key}:{window}"
                count = self._redis.incr(redis_key)
                if count == 1:
                    self._redis.expire(redis_key, bucket.window_seconds * 2)
                return count <= bucket.limit, max(0, bucket.limit - int(count))
            except Exception as exc:  # noqa: BLE001
                logger.warning("rate_limiter_redis_error", extra={"detail": str(exc)[:160]})
                self._redis = None

        now = time.time()
        events = self._local[key]
        while events and now - events[0] > bucket.window_seconds:
            events.popleft()
        if len(events) >= bucket.limit:
            return False, 0
        events.append(now)
        return True, bucket.limit - len(events)

    def reset(self) -> None:
        self._local.clear()


_limiter: RateLimiter | None = None


def get_rate_limiter() -> RateLimiter:
    global _limiter
    if _limiter is None:
        _limiter = RateLimiter(get_settings())
    return _limiter


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Coarse per-identity limit. Expensive endpoints add a stricter dependency check."""

    _EXEMPT_PATHS = ("/health", "/readiness", "/docs", "/openapi.json", "/redoc")

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        settings = get_settings()
        if not settings.rate_limit_enabled or request.url.path.endswith(self._EXEMPT_PATHS):
            return await call_next(request)

        identity = _identity_key(request)
        allowed, remaining = get_rate_limiter().check(
            f"http:{identity}", Bucket(limit=settings.rate_limit_per_user_per_minute)
        )
        if not allowed:
            logger.warning("rate_limited", extra={"identity": identity, "path": request.url.path})
            return JSONResponse(
                status_code=429,
                content={
                    "error": {
                        "code": ErrorCode.RATE_LIMITED.value,
                        "message": "Rate limit exceeded. Please retry shortly.",
                        "retryable": True,
                        "details": {"limit_per_minute": settings.rate_limit_per_user_per_minute},
                        "request_id": getattr(request.state, "request_id", None),
                    }
                },
                headers={"Retry-After": "30"},
            )
        response = await call_next(request)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        return response


def _identity_key(request: Request) -> str:
    api_key = request.headers.get("x-api-key", "")
    if api_key:
        return f"key:{api_key[:16]}"
    authorization = request.headers.get("authorization", "")
    if authorization:
        return f"tok:{authorization[-24:]}"
    return f"ip:{request.client.host if request.client else 'unknown'}"
