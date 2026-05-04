from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from fastapi import Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel


class ApiMeta(BaseModel):
    timestamp: str
    path: str


class ApiSuccess(BaseModel):
    data: Any


class ApiError(BaseModel):
    code: str
    message: str


class ApiResponse(BaseModel):
    resultType: Literal["SUCCESS", "FAIL"]
    success: ApiSuccess | None
    error: ApiError | None
    meta: ApiMeta


def _timestamp_utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def success_response(request: Request, data: Any, status_code: int = 200) -> JSONResponse:
    payload = ApiResponse(
        resultType="SUCCESS",
        success=ApiSuccess(data=data),
        error=None,
        meta=ApiMeta(timestamp=_timestamp_utc(), path=request.url.path),
    )
    return JSONResponse(status_code=status_code, content=payload.model_dump())


def fail_response(request: Request, code: str, message: str, status_code: int) -> JSONResponse:
    payload = ApiResponse(
        resultType="FAIL",
        success=None,
        error=ApiError(code=code, message=message),
        meta=ApiMeta(timestamp=_timestamp_utc(), path=request.url.path),
    )
    return JSONResponse(status_code=status_code, content=payload.model_dump())
