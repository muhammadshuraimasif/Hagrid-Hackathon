from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="Amaanat API",
    description="Amaanat DPI Relief Assistance Prototype API",
    version="0.1.0",
)

# Prototype banner & CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def add_prototype_header(request, call_next):
    response = await call_next(request)
    response.headers["X-Amaanat-Prototype"] = "true"
    response.headers["X-Amaanat-Warning"] = "PROTOTYPE ONLY - Synthetic data only"
    return response

@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "prototype": True,
        "service": "amaanat-api",
        "version": "0.1.0"
    }
