"""
Tests calling Mock Public Rails Services over real TCP network / HTTP sockets
running in an independent uvicorn subprocess.
PROTOTYPE ONLY. Follows AGENTS.md and docs/BLUEPRINT.md.
"""
import sys
import time
import socket
import subprocess
import uuid
import pytest
import httpx
from sqlalchemy import select
from api.database import AsyncSessionLocal
from api.models import Case, CaseEvent
from api.clients.nadra_client import NadraClient, NadraServiceUnavailableError
from api.clients.raast_client import RaastClient
from api.security import mint_decision_token

def _is_port_open(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex((host, port)) == 0

@pytest.fixture(scope="module")
def real_mock_server():
    host = "127.0.0.1"
    port = 8011
    proc = None

    if not _is_port_open(host, port):
        cmd = [
            sys.executable,
            "-m",
            "uvicorn",
            "mocks.main:app",
            "--host",
            host,
            "--port",
            str(port),
            "--log-level",
            "warning"
        ]
        proc = subprocess.Popen(cmd)
        
        # Wait up to 10 seconds for mock server to be responsive
        started = False
        for _ in range(50):
            if _is_port_open(host, port):
                started = True
                break
            time.sleep(0.2)

        if not started:
            if proc:
                proc.kill()
            pytest.fail("Failed to start mock uvicorn process on port 8011")

    base_url = f"http://{host}:{port}"
    yield base_url

    # Teardown
    if proc:
        proc.terminate()
        try:
            proc.wait(timeout=3)
        except Exception:
            proc.kill()

@pytest.mark.asyncio
async def test_real_http_nadra_lookup(real_mock_server: str):
    """Test 1: Real HTTP NADRA lookup over network socket."""
    client = NadraClient(base_url=real_mock_server)
    citizen = await client.get_citizen("42101-1000001-1")
    assert citizen["name"] == "Muhammad Tariq"
    assert citizen["status"] == "VALID"
    assert citizen["prototype"] is True

@pytest.mark.asyncio
async def test_real_http_raast_idempotent_replay(real_mock_server: str):
    """Test 2: Real HTTP Raast payment hold and idempotent replay."""
    client = RaastClient(base_url=real_mock_server)
    case_id = f"real-http-case-{uuid.uuid4().hex[:6]}"
    amount = 14000.0
    idemp_key = f"real-key-{uuid.uuid4().hex}"
    decision_token = mint_decision_token(case_id=case_id, amount=amount, tenant_id="tenant-prd")

    # 1. First authorisation
    res1 = await client.authorise_hold(
        case_id=case_id,
        amount=amount,
        iban="PK36MOCK12345678901234",
        decision_token=decision_token,
        idempotency_key=idemp_key
    )
    assert res1["status"] == "HELD"
    assert res1["replayed"] is False
    txn_id = res1["transaction_id"]

    # 2. Replay with identical key over network
    res2 = await client.authorise_hold(
        case_id=case_id,
        amount=amount,
        iban="PK36MOCK12345678901234",
        decision_token=decision_token,
        idempotency_key=idemp_key
    )
    assert res2["status"] == "HELD"
    assert res2["replayed"] is True
    assert res2["transaction_id"] == txn_id

@pytest.mark.asyncio
async def test_real_http_chaos_switch_moves_case_to_waiting_for_service(
    real_mock_server: str,
    client: httpx.AsyncClient,
    citizen_prd_token: str
):
    """Test 3: Real HTTP chaos switch turns NADRA off, API moves case to WAITING_FOR_SERVICE."""
    headers_citizen = {"Authorization": f"Bearer {citizen_prd_token}"}
    nadra_client = NadraClient(base_url=real_mock_server, failure_threshold=2, recovery_timeout=1.0)

    # 1. Create a case
    res_case = await client.post("/api/v1/cases", headers=headers_citizen, json={"name": "Real Chaos Case"})
    assert res_case.status_code == 201
    case_id = res_case.json()["id"]

    # 2. Trigger chaos switch on real mock server (500s)
    async with httpx.AsyncClient() as http:
        res_chaos = await http.post(
            f"{real_mock_server}/chaos",
            json={"service": "nadra", "error_500": True}
        )
        assert res_chaos.status_code == 200

    # 3. NADRA client lookup fails and transitions case to WAITING_FOR_SERVICE
    async with AsyncSessionLocal() as session:
        with pytest.raises(NadraServiceUnavailableError):
            await nadra_client.get_citizen(
                cnic="42101-1000001-1",
                case_id=case_id,
                db=session,
                tenant_id="tenant-prd"
            )

        # 4. Confirm case is now WAITING_FOR_SERVICE in database
        case_row = (await session.execute(select(Case).where(Case.id == case_id))).scalars().first()
        assert case_row.status == "WAITING_FOR_SERVICE"

        event = (await session.execute(
            select(CaseEvent).where(CaseEvent.case_id == case_id, CaseEvent.event_type == "service_wait")
        )).scalars().first()
        assert event is not None
        assert "We cannot check your card right now" in event.payload["user_message"]

    # 5. Reset chaos on real mock server
    async with httpx.AsyncClient() as http:
        await http.post(f"{real_mock_server}/chaos/reset")
