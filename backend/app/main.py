from fastapi import FastAPI
from pydantic import BaseModel
from app.ingestion_routes import router
from app.analysis_routes import router as analysis_router

app = FastAPI(title="KillChain AI", version="0.1.0", description="Evidence-linked security log investigation and bounded ingestion.")
app.include_router(router)
app.include_router(analysis_router)


class HealthResponse(BaseModel):
    status: str
    service: str
    version: str


@app.get("/api/health", response_model=HealthResponse)
def health() -> HealthResponse:
    """Process liveness only; does not assert database or Gemini readiness."""
    return HealthResponse(status="ok", service="KillChain AI", version="0.1.0")
