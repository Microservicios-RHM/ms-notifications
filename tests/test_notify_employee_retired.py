import pytest

from app.application.notify_employee_retired import handle_employee_retired
from app.infrastructure.messaging.envelope import EventEnvelope
from tests.conftest import RecordingRepository, test_logger

EMPLOYEE_RETIRED_ENVELOPE = EventEnvelope(
    id="8c0366ef-1e0f-42e7-835f-cd9c4e7d241f",
    type="empleado.retirado",
    version=1,
    occurred_at="2026-06-01T10:00:00.000Z",
    producer="empleados-service",
    data={
        "id": "E001",
        "nombre": "Juan",
        "apellido": "Pérez",
        "email": "juan.perez@empresa.com",
        "numeroEmpleado": "EMP-2026-001",
        "cargo": "Desarrollador Senior",
        "area": "Tecnología",
        "departamentoId": "IT",
        "fechaIngreso": "2026-02-10",
        "estado": "RETIRADO",
        "fechaRetiro": "2026-06-01T10:00:00.000Z",
    },
)


@pytest.mark.asyncio
async def test_crea_notificacion_de_desvinculacion():
    repository = RecordingRepository()

    await handle_employee_retired(EMPLOYEE_RETIRED_ENVELOPE, repository, test_logger)

    assert len(repository.saved) == 1
    event_id, notification = repository.saved[0]
    assert event_id == EMPLOYEE_RETIRED_ENVELOPE.id
    assert notification.tipo == "DESVINCULACION"
    assert notification.destinatario == "juan.perez@empresa.com"
    assert notification.empleado_id == "E001"


@pytest.mark.asyncio
async def test_no_falla_cuando_el_evento_es_duplicado():
    repository = RecordingRepository(already_processed=True)

    await handle_employee_retired(EMPLOYEE_RETIRED_ENVELOPE, repository, test_logger)

    assert len(repository.saved) == 1
