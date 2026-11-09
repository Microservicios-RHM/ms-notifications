from fastapi import APIRouter, Request, Response
from fastapi.responses import JSONResponse

from app.infrastructure.http.schemas import HealthResponse
from app.observability import render_metrics

router = APIRouter()


@router.get("/metrics", include_in_schema=False)
async def metrics() -> Response:
    return Response(
        content=render_metrics(),
        media_type="text/plain; version=0.0.4; charset=utf-8",
    )


@router.get("/health", tags=["Health"], summary="Consultar el estado del servicio")
async def health(request: Request) -> JSONResponse:
    checks = {"database": "DOWN", "broker": "DOWN"}
    try:
        async with request.app.state.database_pool.acquire() as connection:
            await connection.execute("SELECT 1")
        checks["database"] = "UP"
    except Exception:  # noqa: BLE001
        pass
    if getattr(request.app.state, "broker_connected", False):
        checks["broker"] = "UP"
    status = "UP" if all(value == "UP" for value in checks.values()) else "DOWN"
    return JSONResponse(
        status_code=200 if status == "UP" else 503,
        content={"status": status, "service": "notificaciones-service", "checks": checks},
    )
