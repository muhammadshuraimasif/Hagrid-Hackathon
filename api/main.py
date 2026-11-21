import logging
import uuid
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, status, HTTPException
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware

from api.config import settings
from api.database import init_db
from api.seed import seed_data
from api.middleware import RequestIdAndPrototypeMiddleware, RateLimitMiddleware
from api.routers import auth, admin, audit, public, ops, cases, documents, sync, consent

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("amaanat-api")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize DB tables, WAL mode, and audit triggers
    await init_db()
    # Seed default tenants and users
    await seed_data()
    yield

app = FastAPI(
    title="Amaanat DPI API",
    description="Amaanat: Transparent, Fail-Closed DPI Relief Platform (PROTOTYPE ONLY)",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Rate Limiter & Request ID / Prototype Header Middlewares
app.add_middleware(RateLimitMiddleware)
app.add_middleware(RequestIdAndPrototypeMiddleware)

# --- Uniform Error Envelope Handlers ---

from starlette.exceptions import HTTPException as StarletteHTTPException

@app.exception_handler(StarletteHTTPException)
async def starlette_http_exception_handler(request: Request, exc: StarletteHTTPException):
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    detail = exc.detail
    if isinstance(detail, dict):
        code = detail.get("code", "HTTP_ERROR")
        message = detail.get("message", "An error occurred")
    else:
        code_map = {
            400: "BAD_REQUEST",
            401: "UNAUTHORIZED",
            403: "FORBIDDEN",
            404: "NOT_FOUND",
            423: "LOCKED",
            429: "RATE_LIMIT_EXCEEDED",
        }
        code = code_map.get(exc.status_code, "ERROR")
        message = str(detail)

    return JSONResponse(
        status_code=exc.status_code,
        content={
            "code": code,
            "message": message,
            "request_id": request_id,
        },
        headers={
            "X-Request-ID": request_id,
            "X-Amaanat-Prototype": "true",
        }
    )

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return await starlette_http_exception_handler(request, exc)

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "code": "VALIDATION_ERROR",
            "message": "Invalid request payload or parameters",
            "request_id": request_id,
        },
        headers={
            "X-Request-ID": request_id,
            "X-Amaanat-Prototype": "true",
        }
    )

@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    logger.error(f"Unhandled exception [{request_id}]: {exc}", exc_info=True)
    # Fail closed: No internal stack trace or debug data is leaked to client
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "code": "INTERNAL_SERVER_ERROR",
            "message": "An internal server error occurred",
            "request_id": request_id,
        },
        headers={
            "X-Request-ID": request_id,
            "X-Amaanat-Prototype": "true",
        }
    )

# Include Routers
app.include_router(ops.router)
app.include_router(auth.router)
app.include_router(admin.router)
app.include_router(audit.router)
app.include_router(public.router)
app.include_router(cases.router)
app.include_router(documents.router)
app.include_router(sync.router)
app.include_router(consent.router)
