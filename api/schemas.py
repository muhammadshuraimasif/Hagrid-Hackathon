from datetime import datetime
from typing import List, Optional, Any
from pydantic import BaseModel, EmailStr, Field

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
