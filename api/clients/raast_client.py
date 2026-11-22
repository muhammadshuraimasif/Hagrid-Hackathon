"""
Capability-gated Raast Payment Client.
Refuses any payout or hold authorisation call without a valid short-lived HMAC decision token
minted strictly for that exact case and amount.
"""
import httpx
from typing import Optional, Dict, Any

from api.config import settings
from api.clients.circuit_breaker import CircuitBreaker
from api.clients.http_client import ResilientHttpClient
from api.security import verify_decision_token

class PaymentSecurityException(Exception):
    """Raised when payment is refused due to invalid or mismatched capability token."""
    pass

class RaastClient:
    def __init__(
        self,
        base_url: Optional[str] = None,
        transport: Optional[httpx.AsyncBaseTransport] = None,
        failure_threshold: int = 3,
        recovery_timeout: float = 2.0
    ):
        url = base_url or settings.RAAST_SERVICE_URL or settings.effective_mock_services_url
        self.circuit_breaker = CircuitBreaker(
            name="raast",
            failure_threshold=failure_threshold,
            recovery_timeout=recovery_timeout
        )
        self.http_client = ResilientHttpClient(
            base_url=url,
            circuit_breaker=self.circuit_breaker,
            transport=transport
        )

    async def lookup_account_title(self, iban: str, cnic: Optional[str] = None) -> Dict[str, Any]:
        """Verify account title matching claimant before initiating hold."""
        resp = await self.http_client.execute(
            method="POST",
            endpoint="/raast/account-title",
            json_data={"iban": iban, "cnic": cnic}
        )
        return resp.json()

    async def authorise_hold(
        self,
        case_id: str,
        amount: float,
        iban: str,
        decision_token: str,
        idempotency_key: str,
        narrative: Optional[str] = "Relief Grant Auto Hold"
    ) -> Dict[str, Any]:
        """
        Authorises a reversible hold on Raast.
        MANDATORY: Verifies cryptographic capability token for this exact case and amount.
        Refuses execution if token is missing, expired, or minted for another case.
        """
        if not decision_token:
            raise PaymentSecurityException("Payment refused: Missing decision capability token.")

        try:
            verify_decision_token(
                token=decision_token,
                expected_case_id=case_id,
                expected_amount=amount
            )
        except ValueError as err:
            raise PaymentSecurityException(f"Payment refused: {str(err)}")

        resp = await self.http_client.execute(
            method="POST",
            endpoint="/raast/authorise",
            headers={"Idempotency-Key": idempotency_key},
            json_data={
                "case_id": case_id,
                "amount": amount,
                "iban": iban,
                "decision_token": decision_token,
                "narrative": narrative
            }
        )
        return resp.json()

    async def release_hold(
        self,
        transaction_id: str,
        idempotency_key: str
    ) -> Dict[str, Any]:
        """Releases a reversible hold to PAID status."""
        resp = await self.http_client.execute(
            method="POST",
            endpoint="/raast/release",
            headers={"Idempotency-Key": idempotency_key},
            json_data={"transaction_id": transaction_id}
        )
        return resp.json()

    async def reverse_hold(
        self,
        transaction_id: str,
        reason: str,
        idempotency_key: str
    ) -> Dict[str, Any]:
        """Reverses an existing hold."""
        resp = await self.http_client.execute(
            method="POST",
            endpoint="/raast/reverse",
            headers={"Idempotency-Key": idempotency_key},
            json_data={"transaction_id": transaction_id, "reason": reason}
        )
        return resp.json()
