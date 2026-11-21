import os
import hashlib
from typing import List
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.database import get_db
from api.models import User, Document, Case
from api.schemas import DocumentInit, DocumentOut
from api.dependencies import get_current_user
from api.audit import record_audit_event

router = APIRouter(prefix="/api/v1/documents", tags=["Documents"])

UPLOAD_DIR = "./uploads"
ALLOWED_MIMES = {
    "image/jpeg": b"\xff\xd8\xff",
    "image/png": b"\x89PNG\r\n\x1a\n",
    "application/pdf": b"%PDF-",
}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB

@router.post("/init", response_model=DocumentOut, status_code=status.HTTP_201_CREATED)
async def init_upload(
    payload: DocumentInit,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    if payload.mime_type not in ALLOWED_MIMES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "INVALID_FILE_TYPE", "message": f"Unsupported MIME type. Allowed: {list(ALLOWED_MIMES.keys())}"}
        )
    if payload.file_size > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "FILE_TOO_LARGE", "message": f"File exceeds maximum allowed size of {MAX_FILE_SIZE} bytes"}
        )

    doc = Document(
        tenant_id=current_user.tenant_id,
        case_id=payload.case_id,
        uploader_id=current_user.id,
        filename=payload.filename,
        mime_type=payload.mime_type,
        file_size=payload.file_size,
        chunk_count=max(1, payload.chunk_count),
        chunks_received=[],
        is_complete=False,
    )
    db.add(doc)
    await db.commit()
    await db.refresh(doc)

    # Ensure doc upload dir exists
    doc_dir = os.path.join(UPLOAD_DIR, doc.id)
    os.makedirs(doc_dir, exist_ok=True)

    return doc

@router.put("/{document_id}/chunks/{chunk_index}")
async def upload_chunk(
    document_id: str,
    chunk_index: int,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(Document).where(Document.id == document_id, Document.tenant_id == current_user.tenant_id))
    doc = result.scalars().first()
    if not doc:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "Document not found"})

    if chunk_index < 0 or chunk_index >= doc.chunk_count:
        raise HTTPException(status_code=400, detail={"code": "INVALID_CHUNK_INDEX", "message": "Chunk index out of bounds"})

    chunk_bytes = await request.body()
    if not chunk_bytes:
        raise HTTPException(status_code=400, detail={"code": "EMPTY_CHUNK", "message": "Chunk body is empty"})

    doc_dir = os.path.join(UPLOAD_DIR, doc.id)
    os.makedirs(doc_dir, exist_ok=True)
    chunk_path = os.path.join(doc_dir, f"chunk_{chunk_index}.part")
    
    with open(chunk_path, "wb") as f:
        f.write(chunk_bytes)

    received = set(doc.chunks_received or [])
    received.add(chunk_index)
    doc.chunks_received = sorted(list(received))
    await db.commit()

    return {
        "status": "ok",
        "document_id": doc.id,
        "chunk_index": chunk_index,
        "received_chunks": doc.chunks_received,
    }

@router.post("/{document_id}/complete", response_model=DocumentOut)
async def complete_upload(
    document_id: str,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    request_id = getattr(request.state, "request_id", None)
    result = await db.execute(select(Document).where(Document.id == document_id, Document.tenant_id == current_user.tenant_id))
    doc = result.scalars().first()
    if not doc:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "Document not found"})

    received = set(doc.chunks_received or [])
    expected = set(range(doc.chunk_count))
    missing = expected - received
    if missing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "MISSING_CHUNKS", "message": f"Upload incomplete. Missing chunk indices: {sorted(list(missing))}"}
        )

    doc_dir = os.path.join(UPLOAD_DIR, doc.id)
    final_path = os.path.join(doc_dir, doc.filename)

    # Assemble chunks
    hasher = hashlib.sha256()
    with open(final_path, "wb") as out_f:
        for i in range(doc.chunk_count):
            c_path = os.path.join(doc_dir, f"chunk_{i}.part")
            with open(c_path, "rb") as in_f:
                chunk = in_f.read()
                hasher.update(chunk)
                out_f.write(chunk)

    # Magic byte validation
    expected_magic = ALLOWED_MIMES.get(doc.mime_type)
    with open(final_path, "rb") as f:
        header = f.read(len(expected_magic))
    
    if not header.startswith(expected_magic):
        # Clean up corrupted/spoofed file
        if os.path.exists(final_path):
            os.remove(final_path)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "INVALID_FILE_TYPE", "message": "File magic bytes do not match declared MIME type"}
        )

    doc.sha256 = hasher.hexdigest()
    doc.storage_path = final_path
    doc.is_complete = True
    await db.commit()
    await db.refresh(doc)

    await record_audit_event(
        actor_type="user",
        action="document.uploaded",
        entity_type="document",
        actor_id=current_user.id,
        entity_id=doc.id,
        request_id=request_id,
        tenant_id=doc.tenant_id,
    )

    return doc
