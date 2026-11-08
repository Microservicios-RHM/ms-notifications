from fastapi import APIRouter, Response

from app.infrastructure.http.schemas import HealthResponse

router = APIRouter()


@router.get("/metrics", include_in_schema=False)
async def metrics() -> Response:
    return Response(
        content=(
            "# HELP rhm_notifications_service_info Static service identity metric\n"
            "# TYPE rhm_notifications_service_info gauge\n"
            'rhm_notifications_service_info{service="notificaciones-service"} 1\n'
        ),
        media_type="text/plain; version=0.0.4; charset=utf-8",
    )


@router.get("/health", tags=["Health"], summary="Consultar el estado del servicio", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse()
