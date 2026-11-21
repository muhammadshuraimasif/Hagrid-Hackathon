import time
import math
import uuid
import json
from collections import defaultdict, deque
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response, JSONResponse
from api.config import settings

# In-memory sliding window rate limiter
# Structure: key -> deque of timestamps
_rate_limit_windows = defaultdict(deque)

class RequestIdAndPrototypeMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Extract or generate Request ID
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        request.state.request_id = request_id

        response = await call_next(request)

        # Append headers to every outgoing response
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Amaanat-Prototype"] = "true"
        response.headers["X-Amaanat-Warning"] = settings.PROTOTYPE_WARNING
        return response


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, requests_per_minute: int = None):
        super().__init__(app)
        self.limit = requests_per_minute or settings.RATE_LIMIT_PER_MINUTE
        self.window_seconds = 60

    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        # Exempt health, ready, docs, and openapi
        if path in ["/health", "/ready", "/docs", "/openapi.json"] or path.startswith("/docs/"):
            return await call_next(request)

        # Identifier: API Key or Client IP
        api_key = request.headers.get("X-API-Key")
        if api_key:
            client_id = f"key:{api_key[:12]}"
        else:
            client_ip = request.client.host if request.client else "unknown"
            client_id = f"ip:{client_ip}"

        now = time.time()
        window_start = now - self.window_seconds
        timestamps = _rate_limit_windows[client_id]

        # Purge timestamps outside sliding window
        while timestamps and timestamps[0] < window_start:
            timestamps.popleft()

        # Check limit
        if len(timestamps) >= self.limit:
            oldest_in_window = timestamps[0]
            retry_after = max(1, math.ceil(oldest_in_window + self.window_seconds - now))
            request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
            
            error_payload = {
                "code": "RATE_LIMIT_EXCEEDED",
                "message": f"Rate limit exceeded. Maximum {self.limit} requests per minute.",
                "request_id": request_id,
                "retry_after": retry_after
            }
            return JSONResponse(
                status_code=429,
                content=error_payload,
                headers={
                    "Retry-After": str(retry_after),
                    "X-Request-ID": request_id,
                    "X-Amaanat-Prototype": "true",
                }
            )

        # Record this request
        timestamps.append(now)
        return await call_next(request)
