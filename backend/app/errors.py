"""A single English error shape for every API failure.

Responses always look like::

    {"error": {"code": "project_not_found", "message": "..."}}

The message is application-owned text and is always English, regardless of the
operating system or browser language.
"""

import logging
import sqlite3

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

GENERIC_MESSAGES = {
    404: "The requested resource was not found.",
    405: "That action is not supported for this resource.",
    500: "The local backend could not complete the request.",
}


class AppError(Exception):
    """An expected failure with an English message meant for the user."""

    def __init__(self, status_code: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message


def error_response(status_code: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"error": {"code": code, "message": message}},
    )


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(OSError)
    @app.exception_handler(sqlite3.Error)
    @app.exception_handler(ValueError)
    async def _storage_error(_: Request, error: Exception) -> JSONResponse:
        logging.exception("The local workspace storage request failed.", exc_info=error)
        return error_response(500, "storage_failed", "The workspace data could not be accessed. Check the application logs and try again.")

    @app.exception_handler(Exception)
    async def _unexpected_error(_: Request, error: Exception) -> JSONResponse:
        logging.exception("The local backend request failed.", exc_info=error)
        return error_response(500, "internal_error", GENERIC_MESSAGES[500])

    @app.exception_handler(AppError)
    async def _app_error(_: Request, error: AppError) -> JSONResponse:
        return error_response(error.status_code, error.code, error.message)

    @app.exception_handler(RequestValidationError)
    async def _validation_error(_: Request, error: RequestValidationError) -> JSONResponse:
        first = error.errors()[0] if error.errors() else {}
        message = str(first.get("msg") or "The request could not be understood.")
        message = message.removeprefix("Value error, ")
        if not message.endswith("."):
            message = f"{message}."
        return error_response(422, "invalid_request", message)

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(_: Request, error: StarletteHTTPException) -> JSONResponse:
        message = GENERIC_MESSAGES.get(
            error.status_code, "The local backend could not complete the request."
        )
        if isinstance(error.detail, str) and error.status_code not in GENERIC_MESSAGES:
            message = error.detail
        return error_response(error.status_code, f"http_{error.status_code}", message)
