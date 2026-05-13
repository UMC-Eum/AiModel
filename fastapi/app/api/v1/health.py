from fastapi import APIRouter, Request

from app.core.exceptions import AppException
from app.core.response import success_response
from app.services.storage import check_mysql_health

router = APIRouter(tags=["health"])


@router.get("/v1/health/db")
async def database_health(request: Request):
    status = await check_mysql_health()
    if status.get("status") == "error":
        raise AppException(
            code="HEALTH-001",
            message=f"MySQL 연결 확인 실패: {status.get('reason', 'unknown')}",
            status_code=503,
        )
    return success_response(request, status)
