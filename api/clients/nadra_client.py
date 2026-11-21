"""
Resilient NADRA Identity Client.
Handles circuit breaking, retries, and automatic WAITING_FOR_SERVICE fail-closed transitions.
"""
import uuid
import httpx
from typing import Optional, Dict, Any, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

from api.config import settings
from api.clients.circuit_breaker import CircuitBreaker, CircuitBreakerOpenError
from api.clients.http_client import ResilientHttpClient
from api.models import Case, CaseEvent
from api.audit import record_audit_event

class NadraServiceUnavailableError(Exception):
    """Raised when NADRA service is unreachable or degraded."""
    pass

class NadraClient:
    def __init__(
        self,
        base_url: Optional[str] = None,
        transport: Optional[httpx.AsyncBaseTransport] = None,
        failure_threshold: int = 3,
        recovery_timeout: float = 2.0
    ):
        url = base_url or settings.MOCK_SERVICES_URL
        self.circuit_breaker = CircuitBreaker(
            name="nadra",
            failure_threshold=failure_threshold,
            recovery_timeout=recovery_timeout
        )
        self.http_client = ResilientHttpClient(
            base_url=url,
            circuit_breaker=self.circuit_breaker,
            transport=transport
        )

    async def get_citizen(
        self,
        cnic: str,
        case_id: Optional[str] = None,
        db: Optional[AsyncSession] = None,
        tenant_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Lookup citizen in NADRA registry.
        If service is unavailable after retries, transitions the case to WAITING_FOR_SERVICE.
        """
        try:
            resp = await self.http_client.execute(
                method="GET",
                endpoint=f"/nadra/citizen/{cnic}"
            )
            return resp.json()
        except (httpx.RequestError, httpx.HTTPStatusError, CircuitBreakerOpenError, Exception) as exc:
            # Service failure or timeout or breaker open
            if case_id and db and tenant_id:
                await self._transition_to_waiting_for_service(
                    case_id=case_id,
                    db=db,
                    tenant_id=tenant_id,
                    reason=str(exc)
                )
            raise NadraServiceUnavailableError(
                f"We cannot check your card right now; we will continue automatically. ({str(exc)})"
            )

    async def verify_qr(
        self,
        qr_payload: str,
        expected_cnic: Optional[str] = None,
        expected_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """Verify signed QR code payload against mock NADRA public key."""
        try:
            resp = await self.http_client.execute(
                method="POST",
                endpoint="/nadra/verify-qr",
                json_data={
                    "qr_payload": qr_payload,
                    "expected_cnic": expected_cnic,
                    "expected_name": expected_name
                }
            )
            if resp.status_code == 400:
                err = resp.json().get("detail", {})
                msg = err.get("message", "QR forgery detected") if isinstance(err, dict) else str(err)
                raise ValueError(msg)
            return resp.json()
        except ValueError:
            raise
        except Exception as exc:
            raise NadraServiceUnavailableError(f"QR verification failed: {str(exc)}")

    async def _transition_to_waiting_for_service(
        self,
        case_id: str,
        db: AsyncSession,
        tenant_id: Optional[str],
        reason: str
    ):
        """Move case safely to WAITING_FOR_SERVICE and inform claimant."""
        query = select(Case).where(Case.id == case_id)
        if tenant_id:
            query = query.where((Case.tenant_id == tenant_id) | (Case.tenant_id == f"tenant-{tenant_id}"))
        case_res = await db.execute(query)
        case = case_res.scalars().first()
        if case and case.status != "WAITING_FOR_SERVICE":
            real_tenant_id = case.tenant_id
            case.status = "WAITING_FOR_SERVICE"
            event = CaseEvent(
                case_id=case.id,
                tenant_id=real_tenant_id,
                client_uuid=str(uuid.uuid4()),
                event_type="service_wait",
                payload={
                    "service": "NADRA",
                    "reason": reason,
                    "user_message": "We cannot check your card right now; we will continue automatically."
                }
            )
            db.add(event)
            await db.commit()

            await record_audit_event(
                actor_type="system",
                action="case.waiting_for_service",
                entity_type="case",
                entity_id=case_id,
                tenant_id=real_tenant_id,
            )

    async def resume_waiting_cases(
        self,
        db: AsyncSession,
        tenant_id: Optional[str] = None
    ) -> List[str]:
        """
        Finds cases stuck in WAITING_FOR_SERVICE, verifies if NADRA is now healthy,
        and transitions them back to CHECKING.
        """
        # 1. Health check probe
        try:
            resp = await self.http_client.execute(method="GET", endpoint="/health")
            if resp.status_code != 200:
                return []
        except Exception:
            return []

        # 2. Query waiting cases
        query = select(Case).where(Case.status == "WAITING_FOR_SERVICE")
        if tenant_id:
            query = query.where((Case.tenant_id == tenant_id) | (Case.tenant_id == f"tenant-{tenant_id}"))
        res = await db.execute(query)
        waiting_cases = res.scalars().all()
        resumed_ids = []

        for c in waiting_cases:
            c.status = "CHECKING"
            event = CaseEvent(
                case_id=c.id,
                tenant_id=c.tenant_id,
                client_uuid=str(uuid.uuid4()),
                event_type="service_resumed",
                payload={
                    "service": "NADRA",
                    "user_message": "NADRA identity service is back online. Resuming case verification."
                }
            )
            db.add(event)
            resumed_ids.append(c.id)

        if resumed_ids:
            await db.commit()
            for cid in resumed_ids:
                await record_audit_event(
                    actor_type="system",
                    action="case.resumed_from_wait",
                    entity_type="case",
                    entity_id=cid,
                    tenant_id=tenant_id,
                )

        return resumed_ids
