import time
from collections import defaultdict
from threading import Lock

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

SERVICE = "notificaciones-service"
_lock = Lock()
_requests: dict[tuple[str, str], int] = defaultdict(int)
_durations: dict[str, float] = defaultdict(float)
_events: dict[tuple[str, str], int] = defaultdict(int)


class MetricsMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        started = time.perf_counter()
        response = await call_next(request)
        if request.url.path != "/metrics":
            observe_http(request.method, response.status_code, time.perf_counter() - started)
        return response


def observe_http(method: str, status: int, duration: float) -> None:
    with _lock:
        _requests[(method, str(status))] += 1
        _durations[method] += duration


def observe_event(event_type: str, outcome: str) -> None:
    with _lock:
        _events[(event_type, outcome)] += 1


def render_metrics() -> str:
    with _lock:
        lines = [
            "# HELP rhm_service_info Static service identity metric",
            "# TYPE rhm_service_info gauge",
            f'rhm_service_info{{service="{SERVICE}"}} 1',
            "# HELP rhm_http_requests_total HTTP requests by method and status",
            "# TYPE rhm_http_requests_total counter",
        ]
        for (method, status), value in sorted(_requests.items()):
            lines.append(f'rhm_http_requests_total{{service="{SERVICE}",method="{method}",status="{status}"}} {value}')
        lines.extend(["# HELP rhm_http_request_duration_seconds_sum Cumulative HTTP request duration", "# TYPE rhm_http_request_duration_seconds_sum counter"])
        for method, value in sorted(_durations.items()):
            lines.append(f'rhm_http_request_duration_seconds_sum{{service="{SERVICE}",method="{method}"}} {value:.6f}')
        lines.extend(["# HELP rhm_events_total Events handled by outcome", "# TYPE rhm_events_total counter"])
        for (event_type, outcome), value in sorted(_events.items()):
            lines.append(f'rhm_events_total{{service="{SERVICE}",event_type="{event_type}",outcome="{outcome}"}} {value}')
        return "\n".join(lines) + "\n"
