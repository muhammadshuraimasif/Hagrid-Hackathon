"""
Automated tests for Part 2: Mock services, Chaos engineering, Circuit Breaker,
Capability-gated payments, and Resilient Clients.
"""
import pytest
import asyncio
import uuid
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from mocks.main import app as mocks_app
from mocks.chaos import chaos_controller
from mocks.synthetic_data import sign_qr_payload, SYNTHETIC_CITIZENS
from api.clients.circuit_breaker import CircuitBreaker, CircuitBreakerOpenError, CircuitState
from api.clients.nadra_client import NadraClient, NadraServiceUnavailableError
from api.clients.raast_client import RaastClient, PaymentSecurityException
from api.clients.sms_client import SmsClient
from api.security import mint_decision_token, verify_decision_token
from api.models import Case, CaseEvent, AuditLog

@pytest.fixture(autouse=True)
def reset_chaos_fixture():
    chaos_controller.reset()
    yield
    chaos_controller.reset()

@pytest.fixture
def mock_transport():
    return ASGITransport(app=mocks_app)

@pytest.mark.asyncio
async def test_mock_nadra_citizen_lookup_and_synthetic_variants(mock_transport):
    client = NadraClient(base_url="http://mock-service", transport=mock_transport)

    # 1. Lookup Muhammad Tariq variant
    citizen1 = await client.get_citizen("42101-1000001-1")
    assert citizen1["name"] == "Muhammad Tariq"
    assert citizen1["status"] == "VALID"
    assert citizen1["is_stale"] is False

    # 2. Lookup Mohammad Tariq variant
    citizen2 = await client.get_citizen("42101-1000002-1")
    assert citizen2["name"] == "Mohammad Tariq"

    # 3. Lookup Mohd Tariq variant
    citizen4 = await client.get_citizen("42101-1000004-1")
    assert citizen4["name"] == "Mohd Tariq"

    # 4. QR Verification - authentic
    qr_res = await client.verify_qr(
        qr_payload=citizen1["qr_payload"],
        expected_cnic="42101-1000001-1",
        expected_name="Muhammad Tariq"
    )
    assert qr_res["is_authentic"] is True

    # 5. QR Verification - forged / tampered
    with pytest.raises(ValueError):
        await client.verify_qr(qr_payload="TAMPERED_B64_PAYLOAD")

@pytest.mark.asyncio
async def test_chaos_modes(mock_transport, client: AsyncClient, admin_prd_token: str):
    headers_admin = {"Authorization": f"Bearer {admin_prd_token}"}
    nadra_client = NadraClient(
        base_url="http://mock-service",
        transport=mock_transport,
        failure_threshold=5,
        recovery_timeout=2.0
    )

    # 1. Chaos Mode: 500 error injection via admin API
    res_chaos = await client.post(
        "/api/v1/admin/chaos",
        headers=headers_admin,
        json={"service": "nadra", "error_500": True}
    )
    assert res_chaos.status_code == 200
    assert res_chaos.json()["updated"]["error_500"] is True

    # Calling NADRA now fails
    with pytest.raises(NadraServiceUnavailableError):
        await nadra_client.get_citizen("42101-1000001-1")

    # 2. Reset chaos
    res_reset = await client.post(
        "/api/v1/admin/chaos",
        headers=headers_admin,
        json={"reset": True}
    )
    assert res_reset.status_code == 200
    assert res_reset.json()["chaos"]["nadra"]["error_500"] is False

    # Reset breaker after simulated downtime
    nadra_client.circuit_breaker.reset()

    # Calling NADRA succeeds again
    cit = await nadra_client.get_citizen("42101-1000001-1")
    assert cit["name"] == "Muhammad Tariq"

    # 3. Chaos Mode: Stale data
    await client.post(
        "/api/v1/admin/chaos",
        headers=headers_admin,
        json={"service": "nadra", "stale_data": True}
    )
    cit_stale = await nadra_client.get_citizen("42101-1000001-1")
    assert cit_stale["is_stale"] is True
    assert cit_stale["status"] == "EXPIRED"

@pytest.mark.asyncio
async def test_circuit_breaker_opens_and_closes():
    cb = CircuitBreaker(name="test-breaker", failure_threshold=3, recovery_timeout=0.15)
    assert cb.state == CircuitState.CLOSED
    assert cb.can_execute() is True

    # Record 3 failures
    cb.record_failure()
    assert cb.state == CircuitState.CLOSED
    cb.record_failure()
    assert cb.state == CircuitState.CLOSED
    cb.record_failure()

    # Breaker must now be OPEN
    assert cb.state == CircuitState.OPEN
    assert cb.can_execute() is False

    # Wait for recovery timeout
    await asyncio.sleep(0.2)
    assert cb.can_execute() is True
    assert cb.state == CircuitState.HALF_OPEN

    # Success in HALF_OPEN resets to CLOSED
    cb.record_success()
    assert cb.state == CircuitState.CLOSED
    assert cb.failure_count == 0

from api.database import AsyncSessionLocal

@pytest.mark.asyncio
async def test_waiting_for_service_and_auto_resume(
    mock_transport,
    client: AsyncClient,
    citizen_prd_token: str
):
    headers = {"Authorization": f"Bearer {citizen_prd_token}"}
    nadra_client = NadraClient(
        base_url="http://mock-service",
        transport=mock_transport,
        failure_threshold=2,
        recovery_timeout=1.0
    )

    # 1. Citizen creates a case
    res_case = await client.post("/api/v1/cases", json={"name": "Waiting Service Case"}, headers=headers)
    case_data = res_case.json()
    case_id = case_data["id"]
    tenant_id = case_data.get("tenant_id") or "tenant-prd"

    # 2. Inject NADRA failure (500s)
    chaos_controller.update_service_chaos("nadra", error_500=True)

    # 3. Verification attempt encounters failure and automatically transitions case to WAITING_FOR_SERVICE
    async with AsyncSessionLocal() as session:
        with pytest.raises(NadraServiceUnavailableError) as exc_info:
            await nadra_client.get_citizen(
                cnic="42101-1000001-1",
                case_id=case_id,
                db=session,
                tenant_id=tenant_id
            )
        assert "We cannot check your card right now" in str(exc_info.value)

    # 4. Check case status in DB
    async with AsyncSessionLocal() as session:
        case = (await session.execute(select(Case).where(Case.id == case_id))).scalars().first()
        assert case.status == "WAITING_FOR_SERVICE"

        # Check case event
        event = (await session.execute(
            select(CaseEvent).where(CaseEvent.case_id == case_id, CaseEvent.event_type == "service_wait")
        )).scalars().first()
        assert event is not None
        assert "We cannot check your card right now" in event.payload["user_message"]

    # 5. Service recovers
    chaos_controller.reset()
    nadra_client.circuit_breaker.reset()

    # 6. Auto-resume resumes waiting cases
    async with AsyncSessionLocal() as session:
        resumed_ids = await nadra_client.resume_waiting_cases(db=session, tenant_id=tenant_id)
        assert case_id in resumed_ids

    # 7. Confirm case is now back in CHECKING
    async with AsyncSessionLocal() as session:
        case = (await session.execute(select(Case).where(Case.id == case_id))).scalars().first()
        assert case.status == "CHECKING"

@pytest.mark.asyncio
async def test_raast_account_title_lookup_returns_holder_name(mock_transport):
    raast = RaastClient(base_url="http://mock-service", transport=mock_transport)

    # Known synthetic accounts
    title_res = await raast.lookup_account_title("PK36MOCK12345678901234")
    assert title_res["account_title"] == "Zainab Bibi"
    assert title_res["status"] == "ACTIVE"

    title_res2 = await raast.lookup_account_title("PK36MOCK99999999999999")
    assert title_res2["account_title"] == "Muhammad Tariq"

@pytest.mark.asyncio
async def test_raast_idempotent_replay_pays_once(mock_transport):
    raast = RaastClient(base_url="http://mock-service", transport=mock_transport)
    case_id = f"case-{uuid.uuid4().hex[:8]}"
    amount = 25000.0
    idempotency_key = f"idemp-{uuid.uuid4().hex}"

    token = mint_decision_token(case_id=case_id, amount=amount, tenant_id="prd")

    # First authorisation call
    res1 = await raast.authorise_hold(
        case_id=case_id,
        amount=amount,
        iban="PK36MOCK12345678901234",
        decision_token=token,
        idempotency_key=idempotency_key
    )
    assert res1["status"] == "HELD"
    assert res1["replayed"] is False
    txn_id = res1["transaction_id"]

    # Replayed call with the SAME idempotency key
    res2 = await raast.authorise_hold(
        case_id=case_id,
        amount=amount,
        iban="PK36MOCK12345678901234",
        decision_token=token,
        idempotency_key=idempotency_key
    )
    assert res2["status"] == "HELD"
    assert res2["replayed"] is True
    assert res2["transaction_id"] == txn_id  # Exactly same transaction!

    # Release hold
    rel_key = f"rel-{uuid.uuid4().hex}"
    rel_res = await raast.release_hold(transaction_id=txn_id, idempotency_key=rel_key)
    assert rel_res["status"] == "PAID"
    assert rel_res["replayed"] is False

    # Replayed release call
    rel_res2 = await raast.release_hold(transaction_id=txn_id, idempotency_key=rel_key)
    assert rel_res2["status"] == "PAID"
    assert rel_res2["replayed"] is True

@pytest.mark.asyncio
async def test_payment_refused_without_token_or_with_wrong_case_token(mock_transport):
    raast = RaastClient(base_url="http://mock-service", transport=mock_transport)
    case_a = "case-aaa-111"
    case_b = "case-bbb-222"
    amount = 15000.0

    token_a = mint_decision_token(case_id=case_a, amount=amount, tenant_id="prd")

    # 1. Refused without decision token
    with pytest.raises(PaymentSecurityException) as exc1:
        await raast.authorise_hold(
            case_id=case_a,
            amount=amount,
            iban="PK36MOCK12345678901234",
            decision_token="",
            idempotency_key="key-no-token"
        )
    assert "Missing decision capability token" in str(exc1.value)

    # 2. Refused with token minted for ANOTHER case (Case A token used on Case B)
    with pytest.raises(PaymentSecurityException) as exc2:
        await raast.authorise_hold(
            case_id=case_b,
            amount=amount,
            iban="PK36MOCK12345678901234",
            decision_token=token_a,
            idempotency_key="key-wrong-case"
        )
    assert f"cannot be used for {case_b}" in str(exc2.value)

    # 3. Refused with mismatched amount
    with pytest.raises(PaymentSecurityException) as exc3:
        await raast.authorise_hold(
            case_id=case_a,
            amount=25000.0,  # Token was minted for 15000.0
            iban="PK36MOCK12345678901234",
            decision_token=token_a,
            idempotency_key="key-wrong-amount"
        )
    assert "does not match expected amount" in str(exc3.value)

    # 4. Refused with expired token
    expired_token = mint_decision_token(case_id=case_a, amount=amount, tenant_id="prd", expires_in_seconds=-10)
    with pytest.raises(PaymentSecurityException) as exc4:
        await raast.authorise_hold(
            case_id=case_a,
            amount=amount,
            iban="PK36MOCK12345678901234",
            decision_token=expired_token,
            idempotency_key="key-expired"
        )
    assert "Decision token has expired" in str(exc4.value)

    # 5. Success with valid token for exact case and amount
    res_ok = await raast.authorise_hold(
        case_id=case_a,
        amount=amount,
        iban="PK36MOCK12345678901234",
        decision_token=token_a,
        idempotency_key="key-valid-hold"
    )
    assert res_ok["status"] == "HELD"
    assert res_ok["case_id"] == case_a
