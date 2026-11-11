"""Health Check API (Reto 8): GET /health verifica de verdad la base de datos y el broker.

  200 {"status":"UP","service":"notificaciones-service","checks":{"database":"UP","messageBroker":"UP"}}
  503 {"status":"DOWN", ...}

Cada check tiene un tiempo límite corto: un health check lento degrada al propio servicio.
"""

import asyncio
from collections.abc import Awaitable, Callable

HealthCheck = Callable[[], Awaitable[bool]]

CHECK_TIMEOUT_SECONDS = 2.0


async def _run(check: HealthCheck, timeout: float) -> str:
    try:
        return "UP" if await asyncio.wait_for(check(), timeout) else "DOWN"
    except Exception:  # noqa: BLE001 - cualquier fallo de la dependencia es DOWN
        return "DOWN"


async def evaluate_health(
    service: str, checks: dict[str, HealthCheck], timeout: float = CHECK_TIMEOUT_SECONDS
) -> dict:
    names = list(checks)
    results = await asyncio.gather(*(_run(checks[name], timeout) for name in names))
    report = dict(zip(names, results, strict=True))
    status = "UP" if all(value == "UP" for value in report.values()) else "DOWN"
    return {"status": status, "service": service, "checks": report}
