from fastapi import FastAPI

app = FastAPI(
    title="Amaanat Mock Public Rails Services",
    description="Mock NADRA (Identity), Raast (Payment), and Telco (SMS) services for prototype verification.",
    version="0.1.0"
)

@app.get("/health")
async def health():
    return {"status": "ok", "service": "mocks", "prototype": True}

@app.get("/nadra/verify/{cnic}")
async def mock_nadra_verify(cnic: str):
    """Mock NADRA CNIC lookup."""
    return {
        "prototype": True,
        "cnic": cnic,
        "status": "VALID",
        "name": "Zainab Bibi",
        "family_head_cnic": "42101-1234567-1",
        "is_deceased": False
    }

@app.post("/raast/payout")
async def mock_raast_payout(payload: dict):
    """Mock Raast Payout with title check."""
    return {
        "prototype": True,
        "transaction_id": "TXN-MOCK-987654321",
        "status": "HELD",
        "hold_seconds": 60,
        "account_title_match": True
    }
