"""
Mock SMS/Telco Client.
"""
import httpx
from typing import Optional, Dict, Any, List
from api.config import settings
from api.clients.circuit_breaker import CircuitBreaker
from api.clients.http_client import ResilientHttpClient

class SmsClient:
    def __init__(
        self,
        base_url: Optional[str] = None,
        transport: Optional[httpx.AsyncBaseTransport] = None
    ):
        url = base_url or settings.MOCK_SERVICES_URL
        self.circuit_breaker = CircuitBreaker(name="sms", failure_threshold=3, recovery_timeout=2.0)
        self.http_client = ResilientHttpClient(
            base_url=url,
            circuit_breaker=self.circuit_breaker,
            transport=transport
        )

    async def send_sms(self, to: str, message: str, sender_code: Optional[str] = "8171-MOCK") -> Dict[str, Any]:
        resp = await self.http_client.execute(
            method="POST",
            endpoint="/sms/send",
            json_data={"to": to, "message": message, "sender_code": sender_code}
        )
        return resp.json()

    async def list_messages(self, limit: int = 50) -> List[Dict[str, Any]]:
        resp = await self.http_client.execute(
            method="GET",
            endpoint="/sms/messages",
            params={"limit": limit}
        )
        return resp.json().get("messages", [])

    async def clear_messages(self) -> Dict[str, Any]:
        resp = await self.http_client.execute(method="POST", endpoint="/sms/messages/clear")
        return resp.json()
