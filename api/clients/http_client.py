"""
Resilient HTTP Client with retry with backoff and Circuit Breaker.
"""
import asyncio
import httpx
from typing import Optional, Dict, Any
from api.clients.circuit_breaker import CircuitBreaker, CircuitBreakerOpenError

class ResilientHttpClient:
    def __init__(
        self,
        base_url: str,
        circuit_breaker: CircuitBreaker,
        transport: Optional[httpx.AsyncBaseTransport] = None,
        timeout: float = 2.0,
        max_retries: int = 2,
        backoff_base: float = 0.05
    ):
        self.base_url = base_url.rstrip("/")
        self.circuit_breaker = circuit_breaker
        self.transport = transport
        self.timeout = timeout
        self.max_retries = max_retries
        self.backoff_base = backoff_base

    async def _get_client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            base_url=self.base_url,
            transport=self.transport,
            timeout=self.timeout
        )

    async def execute(
        self,
        method: str,
        endpoint: str,
        headers: Optional[Dict[str, str]] = None,
        json_data: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None
    ) -> httpx.Response:
        """
        Executes an HTTP request guarded by Circuit Breaker and Retries with exponential backoff.
        """
        if not self.circuit_breaker.can_execute():
            raise CircuitBreakerOpenError(
                f"Circuit breaker '{self.circuit_breaker.name}' is OPEN. Fast failing request."
            )

        last_exception = None
        for attempt in range(self.max_retries + 1):
            try:
                async with await self._get_client() as client:
                    resp = await client.request(
                        method=method,
                        url=endpoint,
                        headers=headers,
                        json=json_data,
                        params=params
                    )
                    # 5xx responses count as service failure
                    if resp.status_code >= 500:
                        self.circuit_breaker.record_failure()
                        resp.raise_for_status()

                    # Success (including 2xx, 4xx client errors which mean service itself is healthy)
                    self.circuit_breaker.record_success()
                    return resp

            except (httpx.RequestError, httpx.HTTPStatusError) as exc:
                self.circuit_breaker.record_failure()
                last_exception = exc
                if attempt < self.max_retries:
                    backoff = self.backoff_base * (2 ** attempt)
                    await asyncio.sleep(backoff)
                else:
                    break

        raise last_exception or RuntimeError("Request failed after retries")
