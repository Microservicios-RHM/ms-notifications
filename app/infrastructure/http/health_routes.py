from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app.infrastructure.http.schemas import HealthResponse
from app.observability.health import evaluate_health
from app.observability.tracing import service_name

router = APIRouter()


async def _not_ready() -> bool:
    return False


# Mientras el lifespan no haya conectado la base de datos y el broker, ambos se reportan DOWN.
_STARTING_CHECKS = {"database": _not_ready, "messageBroker": _not_ready}


@router.get(
    "/health",
    tags=["Health"],
    summary="Consultar el estado del servicio y de sus dependencias",
    response_model=HealthResponse,
    responses={503: {"model": HealthResponse, "description": "Alguna dependencia está DOWN"}},
)
async def health(request: Request) -> JSONResponse:
    checks = getattr(request.app.state, "health_checks", _STARTING_CHECKS)
    report = await evaluate_health(service_name(), checks)
    return JSONResponse(report, status_code=200 if report["status"] == "UP" else 503)
