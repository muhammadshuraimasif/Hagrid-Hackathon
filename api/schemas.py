from datetime import datetime
from typing import List, Optional, Any, Dict
from pydantic import BaseModel, Field

class ErrorEnvelope(BaseModel):
    code: str
    message: str
    request_id: str
    retry_after: Optional[int] = None

class LoginRequest(BaseModel):
    email: str
    password: str

class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int = 900  # 15 minutes

class RefreshRequest(BaseModel):
    refresh_token: str

class UserOut(BaseModel):
    id: str
    tenant_id: str
    email: str
    role: str
    language: str
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}

class ApiKeyCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=128)
    scopes: List[str] = Field(default_factory=lambda: ["case_status:read"])

class ApiKeyOut(BaseModel):
    id: str
    tenant_id: str
    name: str
    key_prefix: str
    scopes: List[str]
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}

class ApiKeyCreatedOut(ApiKeyOut):
    api_key: str

class AuditLogOut(BaseModel):
    id: int
    tenant_id: Optional[str]
    actor_type: str
    actor_id: Optional[str]
    action: str
    entity_type: str
    entity_id: Optional[str]
    acting_as: Optional[str]
    request_id: Optional[str]
    prev_hash: str
    hash: str
    created_at: datetime

    model_config = {"from_attributes": True}

class AuditVerifyOut(BaseModel):
    ok: bool
    checked: int
    broken_at_id: Optional[int] = None

class WhoamiOut(BaseModel):
    status: str = "ok"
    tenant_id: str
    key_name: str
    scopes: List[str]

# --- Cases Schemas ---
class CaseCreate(BaseModel):
    person_id: Optional[str] = None
    cnic: Optional[str] = None
    name: Optional[str] = None
    father_name: Optional[str] = None
    dob: Optional[str] = None
    initial_step: Optional[Dict[str, Any]] = None

class CaseStepSave(BaseModel):
    step_data: Dict[str, Any]
    client_uuid: Optional[str] = None

class CaseTransition(BaseModel):
    reason: Optional[str] = None
    client_uuid: Optional[str] = None

class CaseAssign(BaseModel):
    officer_id: str

class CaseOut(BaseModel):
    id: str
    tenant_id: str
    person_id: str
    creator_user_id: str
    assigned_officer_id: Optional[str] = None
    status: str
    step_data: Dict[str, Any]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

class CaseEventOut(BaseModel):
    id: int
    case_id: str
    client_uuid: str
    event_type: str
    payload: Dict[str, Any]
    created_at: datetime

    model_config = {"from_attributes": True}

# --- Document Schemas ---
class DocumentInit(BaseModel):
    filename: str
    mime_type: str
    file_size: int
    chunk_count: int = 1
    case_id: Optional[str] = None

class DocumentOut(BaseModel):
    id: str
    tenant_id: str
    case_id: Optional[str] = None
    filename: str
    mime_type: str
    file_size: int
    chunk_count: int
    chunks_received: List[int]
    is_complete: bool
    sha256: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}

# --- Sync Schemas ---
class SyncEventIn(BaseModel):
    case_id: str
    client_uuid: str
    event_type: str
    payload: Dict[str, Any] = Field(default_factory=dict)
    created_at: Optional[datetime] = None

class SyncPushRequest(BaseModel):
    events: List[SyncEventIn]

class SyncPushResponse(BaseModel):
    status: str = "ok"
    processed: int
    ignored_duplicates: int

class SyncPullResponse(BaseModel):
    events: List[CaseEventOut]
    next_cursor: int

# --- Consent Schemas ---
class ConsentGrantRequest(BaseModel):
    person_id: str
    granted_to_type: str = "department"  # department, helper, api_client
    granted_to_id: Optional[str] = None
    scope: List[str] = Field(default_factory=lambda: ["identity", "contact", "documents", "payment", "status"])
    purpose: str = "DPI Relief Support Grant Application"
    expiry_days: Optional[int] = 30

class ConsentWithdrawRequest(BaseModel):
    person_id: str
    reason: Optional[str] = "Citizen request to withdraw data consent"

class ConsentCorrectionRequest(BaseModel):
    person_id: str
    field_name: str
    suggested_value: str
    reason: str

class ConsentOut(BaseModel):
    id: str
    tenant_id: str
    person_id: str
    granted_to_type: str
    granted_to_id: Optional[str]
    scope: List[str]
    purpose: str
    expiry: Optional[datetime]
    receipt_id: str
    epoch: int
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}

class ConsentEventOut(BaseModel):
    id: int
    tenant_id: str
    consent_id: Optional[str]
    person_id: str
    event_type: str
    epoch: int
    details: Dict[str, Any]
    created_at: datetime

    model_config = {"from_attributes": True}

