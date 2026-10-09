"""Yerel, salt okunur FastAPI uygulamasının oluşturulması."""

from contextlib import asynccontextmanager
from typing import Annotated

import psycopg
from fastapi import FastAPI, Query, Request
from fastapi.exceptions import RequestValidationError, ResponseValidationError
from pydantic import ValidationError
from psycopg_pool import PoolClosed, PoolTimeout, TooManyRequests
from starlette.exceptions import HTTPException
from starlette.responses import JSONResponse

from app.api import database
from app.api.models import (
    ErrorDetail,
    ErrorResponse,
    HealthResponse,
    ProductResponse,
    StatusResponse,
    product_response,
)
from app.contracts import Product, utc_now
from app.database import read

Days = Annotated[int, Query(ge=1, le=366)]


def error_response(status: int, code: str, message: str) -> JSONResponse:
    body = ErrorResponse(detail=ErrorDetail(code=code, message=message))
    return JSONResponse(
        status_code=status,
        content=body.model_dump(mode="json"),
        headers={"Cache-Control": "no-store"},
    )


def create_app() -> FastAPI:
    @asynccontextmanager
    async def lifespan(app):
        pool = database.create_pool()
        app.state.pool = pool
        try:
            pool.open(wait=False)
            yield
        finally:
            pool.close()

    app = FastAPI(
        title="Telefon Fiyat Takibi",
        version="1.0.0",
        lifespan=lifespan,
        responses={status: {"model": ErrorResponse} for status in (404, 422, 500, 503)},
    )

    @app.middleware("http")
    async def no_store(request, call_next):
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        return response

    @app.exception_handler(database.UnavailableError)
    async def unavailable(request, exc):
        return error_response(503, exc.code, exc.message)

    @app.exception_handler(PoolTimeout)
    @app.exception_handler(PoolClosed)
    @app.exception_handler(TooManyRequests)
    async def pool_error(request, exc):
        return error_response(
            503, "pool_unavailable", "Veritabanı bağlantısı şu anda alınamıyor."
        )

    @app.exception_handler(psycopg.Error)
    async def database_error(request, exc):
        return error_response(
            503, "database_unavailable", "Veritabanı şu anda okunamıyor."
        )

    @app.exception_handler(RequestValidationError)
    async def invalid_request(request, exc):
        return error_response(422, "invalid_request", "İstek parametreleri geçersiz.")

    @app.exception_handler(HTTPException)
    async def http_error(request, exc):
        code, message = {
            404: ("not_found", "İstenen adres bulunamadı."),
            405: ("method_not_allowed", "Bu adreste yalnız GET isteği kullanılabilir."),
        }.get(exc.status_code, ("http_error", "İstek tamamlanamadı."))
        return error_response(exc.status_code, code, message)

    @app.exception_handler(ValidationError)
    @app.exception_handler(ResponseValidationError)
    @app.exception_handler(Exception)
    async def internal_error(request, exc):
        return error_response(500, "internal_error", "API cevabı hazırlanamadı.")

    @app.get("/health", response_model=HealthResponse)
    def health(request: Request):
        with request.app.state.pool.connection() as conn:
            database.validate_readiness(conn)
        return HealthResponse()

    @app.get("/api/v1/status", response_model=StatusResponse)
    def status(request: Request):
        with request.app.state.pool.connection() as conn:
            database.validate_readiness(conn)
            result = read.read_run_status(conn)
        return StatusResponse.model_validate(result)

    @app.get("/api/v1/products", response_model=tuple[Product, ...])
    def products(request: Request):
        with request.app.state.pool.connection() as conn:
            database.validate_readiness(conn)
            return read.list_products(conn)

    @app.get("/api/v1/products/{product_key}", response_model=ProductResponse)
    def product(
        request: Request,
        product_key: str,
        history_days: Days = 30,
        cimri_days: Days = 366,
    ):
        with request.app.state.pool.connection() as conn:
            database.validate_readiness(conn)
            snapshot = read.read_product(conn, product_key, history_days, cimri_days)
        if snapshot is None:
            return error_response(404, "product_not_found", "Telefon bulunamadı.")
        return product_response(snapshot, utc_now())

    return app
