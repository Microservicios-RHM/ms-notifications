import pytest

from app.application.notify_employee_created import handle_employee_created
from app.infrastructure.messaging.envelope import EventEnvelope
from tests.conftest import RecordingDirectory, RecordingRepository, test_logger

EMPLOYEE_CREATED_ENVELOPE = EventEnvelope(
    id="3f2a1c9e-7b4d-4e10-9c2a-1a2b3c4d5e6f",
    type="empleado.creado",
    version=1,
    occurred_at="2026-03-01T10:00:00.000Z",
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
        "estado": "ACTIVO",
        "fechaRetiro": None,
    },
)


@pytest.mark.asyncio
async def test_crea_notificacion_bienvenida_y_alimenta_el_directorio():
    repository = RecordingRepository()
    directory = RecordingDirectory()

    await handle_employee_created(EMPLOYEE_CREATED_ENVELOPE, repository, directory, test_logger)

    assert len(repository.saved) == 1
    event_id, notification = repository.saved[0]
    assert event_id == EMPLOYEE_CREATED_ENVELOPE.id
    assert notification.tipo == "BIENVENIDA"
    assert notification.destinatario == "juan.perez@empresa.com"
    assert notification.empleado_id == "E001"
    assert "Juan Pérez" in notification.mensaje

    assert directory.upserts == [("E001", "Juan", "Pérez", "juan.perez@empresa.com")]


@pytest.mark.asyncio
async def test_no_alimenta_el_directorio_cuando_el_evento_es_duplicado():
    repository = RecordingRepository(already_processed=True)
    directory = RecordingDirectory()

    await handle_employee_created(EMPLOYEE_CREATED_ENVELOPE, repository, directory, test_logger)

    assert len(repository.saved) == 1
    assert directory.upserts == []
