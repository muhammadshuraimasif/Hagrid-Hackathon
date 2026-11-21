"""
Mock Public Rails Services (NADRA Identity, Raast Payments, Telco SMS)
PROTOTYPE ONLY - Hagrid's Hackathon '26
All data is strictly synthetic.
"""
import uuid
import datetime
from typing import Dict, Any, List, Optional
from fastapi import FastAPI, Header, HTTPException, status, Query
from pydantic import BaseModel, Field

from mocks.synthetic_data import (
    SYNTHETIC_CITIZENS,
    SYNTHETIC_RAAST_ACCOUNTS,
    verify_qr_payload,
    sign_qr_payload
)
from mocks.chaos import chaos_controller

app = FastAPI(
    title="Amaanat Mock Public Rails Services",
    description="Mock NADRA (Identity), Raast (Payment), and Telco (SMS) services for prototype verification.",
    version="0.2.0"
)

# ----------------- IN-MEMORY STATE -----------------
# Idempotency cache: Idempotency-Key -> Response dict
_raast_idempotency_store: Dict[str, Dict[str, Any]] = {}
# Transaction store: transaction_id -> Details
_raast_transactions: Dict[str, Dict[str, Any]] = {}
# In-memory SMS log
_sms_messages_log: List[Dict[str, Any]] = []


# ----------------- SCHEMAS -----------------
class ChaosUpdateRequest(BaseModel):
    service: str  # "nadra", "raast", "sms"
    latency_ms: Optional[int] = None
    error_500: Optional[bool] = None
    timeout: Optional[bool] = None
    stale_data: Optional[bool] = None
    reset: Optional[bool] = False

class QRVerifyRequest(BaseModel):
    qr_payload: str
    expected_cnic: Optional[str] = None
    expected_name: Optional[str] = None

class AccountTitleRequest(BaseModel):
    iban: str
    cnic: Optional[str] = None

class RaastAuthoriseRequest(BaseModel):
    amount: float
    iban: str
    case_id: str
    decision_token: str
    narrative: Optional[str] = "Relief Grant Auto Hold"

class RaastReleaseRequest(BaseModel):
    transaction_id: str

class RaastReverseRequest(BaseModel):
    transaction_id: str
    reason: str

class SMSSendRequest(BaseModel):
    to: str
    message: str
    sender_code: Optional[str] = "8171-MOCK"


# ----------------- SYSTEM & CHAOS ENDPOINTS -----------------
@app.get("/health")
async def health():
    return {
        "prototype": True,
        "status": "ok",
        "service": "mocks",
        "synthetic_records_loaded": len(SYNTHETIC_CITIZENS)
    }

@app.get("/chaos")
async def get_chaos():
    return {
        "prototype": True,
        "chaos": chaos_controller.get_state()
    }

@app.post("/chaos")
async def update_chaos(req: ChaosUpdateRequest):
    if req.reset:
        chaos_controller.reset()
        return {"prototype": True, "status": "reset", "chaos": chaos_controller.get_state()}

    updated = chaos_controller.update_service_chaos(
        service=req.service,
        latency_ms=req.latency_ms,
        error_500=req.error_500,
        timeout=req.timeout,
        stale_data=req.stale_data
    )
    return {"prototype": True, "service": req.service, "updated": updated}

@app.post("/chaos/reset")
async def reset_chaos():
    chaos_controller.reset()
    return {"prototype": True, "status": "ok", "chaos": chaos_controller.get_state()}


# ----------------- NADRA IDENTITY ENDPOINTS -----------------
@app.get("/nadra/citizens")
async def list_nadra_citizens(limit: int = 50, q: Optional[str] = None):
    results = list(SYNTHETIC_CITIZENS.values())
    if q:
        q_lower = q.lower()
        results = [c for c in results if q_lower in c["name"].lower() or q_lower in c["cnic"]]
    return {"prototype": True, "total": len(results), "citizens": results[:limit]}

@app.get("/nadra/citizen/{cnic}")
async def get_nadra_citizen(cnic: str):
    # Apply chaos
    is_stale = await chaos_controller.apply_chaos("nadra")

    clean_cnic = cnic.strip()
    citizen = SYNTHETIC_CITIZENS.get(clean_cnic)
    if not citizen:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "CITIZEN_NOT_FOUND", "message": f"CNIC {clean_cnic} not registered in NADRA database"}
        )

    res = dict(citizen)
    res["prototype"] = True
    if is_stale:
        # Return stale/expired card indicator
        res["status"] = "EXPIRED"
        res["card_expiry"] = "2020-01-01"
        res["is_stale"] = True
    else:
        res["status"] = "VALID"
        res["card_expiry"] = "2032-12-31"
        res["is_stale"] = False

    return res

@app.post("/nadra/verify-qr")
async def verify_nadra_qr(req: QRVerifyRequest):
    await chaos_controller.apply_chaos("nadra")

    try:
        decoded_payload = verify_qr_payload(req.qr_payload)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "FORGERY_DETECTED", "message": str(e)}
        )

    # Optional cross-checks
    matches_cnic = True
    matches_name = True
    if req.expected_cnic:
        matches_cnic = (decoded_payload.get("cnic") == req.expected_cnic)
    if req.expected_name:
        matches_name = (decoded_payload.get("name", "").lower() == req.expected_name.lower())

    is_authentic = matches_cnic and matches_name
    return {
        "prototype": True,
        "is_authentic": is_authentic,
        "matches_cnic": matches_cnic,
        "matches_name": matches_name,
        "payload": decoded_payload
    }


# ----------------- RAAST PAYMENTS ENDPOINTS -----------------
@app.post("/raast/account-title")
async def lookup_account_title(req: AccountTitleRequest):
    await chaos_controller.apply_chaos("raast")

    clean_iban = req.iban.replace(" ", "").upper()
    acc = SYNTHETIC_RAAST_ACCOUNTS.get(clean_iban)
    if not acc:
        # Default mock fallback title for any standard test IBAN
        holder = "Zainab Bibi" if "1234" in clean_iban else "Muhammad Tariq"
        return {
            "prototype": True,
            "iban": clean_iban,
            "account_title": holder,
            "bank_name": "STATE_MOCK_MICROFINANCE",
            "status": "ACTIVE"
        }

    return {
        "prototype": True,
        "iban": acc["iban"],
        "account_title": acc["account_title"],
        "bank_name": acc["bank_name"],
        "status": acc["status"]
    }

@app.post("/raast/authorise")
async def authorise_payment_hold(
    req: RaastAuthoriseRequest,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key")
):
    await chaos_controller.apply_chaos("raast")

    # Mandatory idempotency key
    if not idempotency_key or not idempotency_key.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "MISSING_IDEMPOTENCY_KEY", "message": "Idempotency-Key header is mandatory for payment authorisation"}
        )

    # Idempotent replay: if key already processed, return stored response
    if idempotency_key in _raast_idempotency_store:
        cached = _raast_idempotency_store[idempotency_key]
        return {**cached, "replayed": True}

    if req.amount <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "INVALID_AMOUNT", "message": "Payment amount must be greater than zero"}
        )

    # Note: Decision token verification is enforced client-side before calling,
    # but mock server also checks non-empty token
    if not req.decision_token:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "TOKEN_REQUIRED", "message": "Decision token missing"}
        )

    now = datetime.datetime.now(datetime.timezone.utc)
    hold_expires = now + datetime.timedelta(seconds=60)
    txn_id = f"RAAST-HOLD-{uuid.uuid4().hex[:12].upper()}"

    resp = {
        "prototype": True,
        "transaction_id": txn_id,
        "status": "HELD",
        "amount": req.amount,
        "iban": req.iban,
        "case_id": req.case_id,
        "hold_seconds": 60,
        "hold_expires_at": hold_expires.isoformat(),
        "created_at": now.isoformat(),
        "replayed": False
    }

    _raast_transactions[txn_id] = resp
    _raast_idempotency_store[idempotency_key] = resp

    return resp

@app.post("/raast/release")
async def release_payment_hold(
    req: RaastReleaseRequest,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key")
):
    await chaos_controller.apply_chaos("raast")

    if not idempotency_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "MISSING_IDEMPOTENCY_KEY", "message": "Idempotency-Key header is mandatory"}
        )

    if idempotency_key in _raast_idempotency_store:
        return {**_raast_idempotency_store[idempotency_key], "replayed": True}

    txn = _raast_transactions.get(req.transaction_id)
    if not txn:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "TRANSACTION_NOT_FOUND", "message": f"Transaction {req.transaction_id} not found"}
        )

    if txn["status"] == "REVERSED":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "ALREADY_REVERSED", "message": "Cannot release a reversed hold"}
        )

    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    txn["status"] = "PAID"
    txn["paid_at"] = now

    resp = {
        "prototype": True,
        "transaction_id": req.transaction_id,
        "status": "PAID",
        "paid_at": now,
        "replayed": False
    }
    _raast_idempotency_store[idempotency_key] = resp
    return resp

@app.post("/raast/reverse")
async def reverse_payment_hold(
    req: RaastReverseRequest,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key")
):
    await chaos_controller.apply_chaos("raast")

    if not idempotency_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "MISSING_IDEMPOTENCY_KEY", "message": "Idempotency-Key header is mandatory"}
        )

    if idempotency_key in _raast_idempotency_store:
        return {**_raast_idempotency_store[idempotency_key], "replayed": True}

    txn = _raast_transactions.get(req.transaction_id)
    if not txn:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "TRANSACTION_NOT_FOUND", "message": f"Transaction {req.transaction_id} not found"}
        )

    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    txn["status"] = "REVERSED"
    txn["reversal_reason"] = req.reason
    txn["reversed_at"] = now

    resp = {
        "prototype": True,
        "transaction_id": req.transaction_id,
        "status": "REVERSED",
        "reason": req.reason,
        "reversed_at": now,
        "replayed": False
    }
    _raast_idempotency_store[idempotency_key] = resp
    return resp


# ----------------- TELCO SMS ENDPOINTS -----------------
@app.post("/sms/send")
async def send_sms(req: SMSSendRequest):
    await chaos_controller.apply_chaos("sms")

    msg_id = f"MSG-{uuid.uuid4().hex[:8].upper()}"
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    entry = {
        "prototype": True,
        "message_id": msg_id,
        "to": req.to,
        "message": req.message,
        "sender_code": req.sender_code or "8171-MOCK",
        "timestamp": now,
        "status": "DELIVERED"
    }
    _sms_messages_log.append(entry)
    return {"prototype": True, "status": "DELIVERED", "message_id": msg_id}

@app.get("/sms/messages")
async def list_sms_messages(limit: int = 50):
    return {"prototype": True, "count": len(_sms_messages_log), "messages": _sms_messages_log[-limit:]}

@app.post("/sms/messages/clear")
async def clear_sms_messages():
    _sms_messages_log.clear()
    return {"prototype": True, "status": "cleared"}
