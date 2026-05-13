from __future__ import annotations

import logging

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError

from app.core.response import fail_response

logger = logging.getLogger(__name__)


class AppException(Exception):
    def __init__(self, *, code: str, message: str, status_code: int) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppException)
    async def handle_app_exception(request: Request, exc: AppException):
        return fail_response(request, code=exc.code, message=exc.message, status_code=exc.status_code)

    @app.exception_handler(RequestValidationError)
    async def handle_validation_exception(request: Request, exc: RequestValidationError):
        logger.warning("request validation failed: %s", exc.errors())
        return fail_response(
            request,
            code="COMMON-422",
            message="요청 본문 또는 파라미터 형식이 올바르지 않습니다.",
            status_code=422,
        )

    @app.exception_handler(HTTPException)
    async def handle_http_exception(request: Request, exc: HTTPException):
        message = exc.detail if isinstance(exc.detail, str) else "요청 처리 중 오류가 발생했습니다."
        code = f"HTTP-{exc.status_code:03d}"
        return fail_response(request, code=code, message=message, status_code=exc.status_code)

    @app.exception_handler(Exception)
    async def handle_unexpected_exception(request: Request, exc: Exception):
        logger.exception("unhandled exception", exc_info=exc)
        return fail_response(
            request,
            code="COMMON-500",
            message="일시적인 오류가 발생했습니다. 잠시 후 다시 시도해 주세요.",
            status_code=500,
        )
