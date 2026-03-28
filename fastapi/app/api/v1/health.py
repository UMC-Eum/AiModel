from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.services.storage import check_mysql_health

router = APIRouter(tags=["health"])


@router.get("/v1/health/db")
async def database_health() -> JSONResponse:
    status = await check_mysql_health()
    http_status = 200 if status.get("status") == "ok" else 503
    return JSONResponse(status_code=http_status, content=status)
