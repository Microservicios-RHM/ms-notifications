import pytest

from app.application.notify_vacation_scheduled import handle_vacation_scheduled
from app.infrastructure.messaging.envelope import EventEnvelope
from tests.conftest import RecordingDirectory, RecordingRepository, test_logger

VACATION_SCHEDULED_ENVELOPE = EventEnvelope(
    id="c1b2a3d4-5e6f-4a7b-8c9d-0e1f2a3b4c5d",
    type="vacaciones.programadas",
    version=1,
    occurred_at="2026-03-01T10:00:00.000Z",
    producer="vacaciones-service",
    data={
        "id": "V-2026-0042",
        "empleadoId": "E001",
        "fechaInicio": "2026-03-15",
        "fechaFin": "2026-03-30",
        "estado": "PROGRAMADA",
        "fechaCreacion": "2026-03-01T10:00:00.000Z",
    },
)


@pytest.mark.asyncio
async def test_crea_notificacion_de_vacaciones_resolviendo_destinatario_por_el_directorio():
    repository = RecordingRepository()
    directory = RecordingDirectory(seed={"E001": ("juan.perez@empresa.com", "Juan", "Pérez")})

    await handle_vacation_scheduled(VACATION_SCHEDULED_ENVELOPE, repository, directory, test_logger)

    assert len(repository.saved) == 1
    event_id, notification = repository.saved[0]
    assert event_id == VACATION_SCHEDULED_ENVELOPE.id
    assert notification.tipo == "VACACIONES"
    assert notification.destinatario == "juan.perez@empresa.com"
    assert "2026-03-15" in notification.mensaje
    assert "2026-03-30" in notification.mensaje


@pytest.mark.asyncio
async def test_omite_la_notificacion_si_el_empleado_no_esta_en_el_directorio():
    repository = RecordingRepository()
    directory = RecordingDirectory()  # vacío: E001 nunca llegó por empleado.creado

    await handle_vacation_scheduled(VACATION_SCHEDULED_ENVELOPE, repository, directory, test_logger)

    assert repository.saved == []


@pytest.mark.asyncio
async def test_no_falla_cuando_el_evento_es_duplicado():
    repository = RecordingRepository(already_processed=True)
    directory = RecordingDirectory(seed={"E001": ("juan.perez@empresa.com", "Juan", "Pérez")})

    await handle_vacation_scheduled(VACATION_SCHEDULED_ENVELOPE, repository, directory, test_logger)

    assert len(repository.saved) == 1
