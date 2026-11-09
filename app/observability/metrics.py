"""Métricas en formato Prometheus (Reto 8) con prometheus_client.

Mismos nombres y etiquetas que en los demás servicios del ecosistema, para que el dashboard de
Grafana use una sola consulta por panel:
  - http_requests_total{method, route, status}
  - http_request_duration_seconds{method, route, status}   (_bucket, _sum, _count)
  - process_cpu_seconds_total, process_resident_memory_bytes  (ProcessCollector por defecto)

`route` es la plantilla (/notificaciones/{empleado_id}), nunca la URL con el id real, para no
crear una serie por empleado (alta cardinalidad).
"""

import time

from fastapi import FastAPI, Request, Response
from prometheus_client import CONTENT_TYPE_LATEST, REGISTRY, CollectorRegistry, Counter, Histogram, generate_latest

UNMATCHED_ROUTE = "unmatched"
BUCKETS = (0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2, 5, 10)


class HttpMetrics:
    def __init__(self, service: str, registry: CollectorRegistry = REGISTRY) -> None:
        self.registry = registry
        labels = ["service", "method", "route", "status"]
        self._service = service
        self.requests = Counter(
            "http_requests_total",
            "Total de peticiones HTTP recibidas, por método, ruta y código de respuesta",
            labels,
            registry=registry,
        )
        self.duration = Histogram(
            "http_request_duration_seconds",
            "Tiempo de respuesta de las peticiones HTTP en segundos",
            labels,
            buckets=BUCKETS,
            registry=registry,
        )

    def observe(self, method: str, route: str, status: int, seconds: float) -> None:
        labels = (self._service, method, route, str(status))
        self.requests.labels(*labels).inc()
        self.duration.labels(*labels).observe(seconds)

    def render(self) -> bytes:
        return generate_latest(self.registry)


def route_template(request: Request) -> str:
    route = request.scope.get("route")
    path = getattr(route, "path", None)
    return path if isinstance(path, str) else UNMATCHED_ROUTE


def install_metrics(app: FastAPI, metrics: HttpMetrics) -> None:
    @app.middleware("http")
    async def record_http_metrics(request: Request, call_next):
        if request.url.path == "/metrics":
            return await call_next(request)
        started = time.perf_counter()
        status = 500
        try:
            response = await call_next(request)
            status = response.status_code
            return response
        finally:
            metrics.observe(request.method, route_template(request), status, time.perf_counter() - started)

    @app.get("/metrics", include_in_schema=False)
    async def prometheus_metrics() -> Response:
        return Response(metrics.render(), media_type=CONTENT_TYPE_LATEST)
