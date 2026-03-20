from fastapi import FastAPI
from app.api.v1 import matches, onboarding

app = FastAPI(title="AI Voice Service", version="0.1.0")

app.include_router(onboarding.router, prefix="/api")
app.include_router(matches.router, prefix="/api")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
