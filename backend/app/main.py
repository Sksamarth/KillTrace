from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="KillChain AI", version="0.1.0", description="Security analysis platform foundation. Processing is not implemented.")


class HealthResponse(BaseModel):
    status: str
    service: str
    version: str


@app.get("/api/health", response_model=HealthResponse)
def health() -> HealthResponse:
    """Process liveness only; does not assert database or Gemini readiness."""
    return HealthResponse(status="ok", service="KillChain AI", version="0.1.0")
