from fastapi import APIRouter

from app.infrastructure.http.schemas import HealthResponse

router = APIRouter()


@router.get("/health", tags=["Health"], summary="Consultar el estado del servicio", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse()
