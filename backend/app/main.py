from fastapi import FastAPI

from backend.app.api.v1.api import api_router

app = FastAPI(title="CP-Hub API", version="0.1.0")
app.include_router(api_router, prefix="/api/v1")


@app.get("/health", tags=["health"], summary="Liveness probe")
async def health() -> dict[str, str]:
    """health check"""
    return {"status": "ok"}
