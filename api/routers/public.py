from fastapi import APIRouter, Depends
from api.models import ApiKey
from api.schemas import WhoamiOut
from api.dependencies import require_scope

router = APIRouter(prefix="/api/v1/public", tags=["Public"])

@router.get("/whoami", response_model=WhoamiOut)
async def whoami(api_key: ApiKey = Depends(require_scope("case_status:read"))):
    return WhoamiOut(
        status="ok",
        tenant_id=api_key.tenant_id,
        key_name=api_key.name,
        scopes=api_key.scopes,
    )
