# Microservicio de notificaciones

Servicio puramente reactivo, construido con Python, FastAPI y PostgreSQL. No expone endpoints de
escritura ni es invocado por REST desde otros servicios: consume eventos de RabbitMQ, simula el
envío de notificaciones mediante un log estructurado, y guarda un historial propio.

Forma parte del ecosistema RHM (Reto 4 — comunicación asincrónica). El contrato de eventos
(envelope, payloads, exchange y bindings) está definido en `docs/event-catalog.md` del repositorio
[rhm-database-infrastructure](https://github.com/Microservicios-RHM/rhm-database-infrastructure).

## Estado

- ✅ Consume `empleado.creado` → notificación `BIENVENIDA`.
- ✅ Consume `empleado.retirado` → notificación `DESVINCULACION`.
- ✅ Consume `vacaciones.programadas` → notificación `VACACIONES` (destinatario resuelto vía el
  directorio local, ver más abajo).
- ✅ Deduplicación por `id` de mensaje (obligatoria, ver más abajo).
- ✅ `GET /notificaciones` y `GET /notificaciones/{empleadoId}`, documentados en OpenAPI/Swagger
  (`/notificaciones/docs`, `/notificaciones/openapi.json`, autogenerados por FastAPI).
- ✅ Registrado en el API Gateway: `http://localhost:8080/notificaciones`, **incluida la
  documentación interactiva** en `http://localhost:8080/notificaciones/docs`.

## Requisitos

- Python 3.13 (el `Dockerfile` usa `python:3.13-slim`; se desarrolló y probó también con 3.14).
- Docker y Docker Compose para ejecutar el servicio real (igual que el resto del ecosistema, la
  infraestructura no publica puertos de bases de datos ni de RabbitMQ salvo su UI de administración
  y el API Gateway).

## Configuración local (tooling, no ejecución)

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env
pytest
```

Los tests usan dobles de prueba (repositorio en memoria, mensajes AMQP falsos), no una conexión
real a PostgreSQL ni a RabbitMQ. Para correr el servicio contra las dependencias reales, el único
flujo soportado es Docker Compose desde `rhm-database-infrastructure`:

```bash
cd ../rhm-database-infrastructure
docker compose up --build
```

Dentro de Docker, PostgreSQL se resuelve como `database-notificaciones:5432` y RabbitMQ como
`message-broker:5672`; ninguno de los dos publica su puerto al host para este servicio.

## Variables de entorno

`.env.example` documenta todas las variables. Las relevantes:

```dotenv
DB_HOST=database-notificaciones
DB_PORT=5432
DB_NAME=notifications_db
DB_USER=notifications_service
DB_PASSWORD=change_notifications_password

BROKER_URL=amqp://admin:admin@message-broker:5672
BROKER_EXCHANGE=rhm.events
BROKER_QUEUE=notificaciones.queue
```

La aplicación valida la configuración al arrancar (`app/config.py`) y falla inmediatamente si falta
una variable requerida (`DB_HOST`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `BROKER_URL`) o si
`BROKER_URL` no tiene el esquema `amqp://`/`amqps://`.

## API

Todas las respuestas usan el mismo envelope que el resto del ecosistema
(`{"success", "message", "data"}`) y el JSON expone los campos en `camelCase`
(`fechaEnvio`, `empleadoId`) aunque internamente el código use `snake_case`.

```bash
curl -i http://localhost:8080/notificaciones
curl -i http://localhost:8080/notificaciones/E001
```

`GET /notificaciones/{empleadoId}` responde `200` con `data: []` si el empleado no tiene
notificaciones — no es un `404`, porque este servicio no valida contra `empleados-service` (rompería
su autonomía como consumidor puramente reactivo); simplemente reporta lo que tiene registrado.

Documentación interactiva — montada bajo `/notificaciones` (no en la raíz) para vivir detrás del
Gateway sin que este necesite ninguna regla especial, ya que `/notificaciones/*` ya se proxea sin
reescritura de ruta:

```text
Swagger UI:     http://localhost:8080/notificaciones/docs
OpenAPI JSON:   http://localhost:8080/notificaciones/openapi.json
```

## Arquitectura

```text
app/
├── domain/
│   ├── entities.py        Notification (dataclass)
│   └── repositories.py    Puertos: Dedup/Query de notificaciones, directorio de empleados
├── application/
│   ├── notify_employee_created.py     empleado.creado → BIENVENIDA (+ alimenta el directorio)
│   ├── notify_employee_retired.py     empleado.retirado → DESVINCULACION
│   ├── notify_vacation_scheduled.py   vacaciones.programadas → VACACIONES
│   └── list_notifications.py          Casos de uso de los endpoints GET
├── infrastructure/
│   ├── http/
│   │   ├── health_routes.py           GET /health
│   │   ├── notification_routes.py     Router factory (recibe los casos de uso, como
│   │   │                              createEmployeeRouter en ms-employees)
│   │   └── schemas.py                 Modelos Pydantic (camelCase) para las respuestas
│   ├── messaging/
│   │   ├── envelope.py              Espejo del envelope del catálogo
│   │   └── consumer.py              Conexión, exchange, cola, bindings, deduplicación en el dispatch
│   └── persistence/
│       ├── database.py                    Pool asyncpg con reintentos y backoff
│       ├── migrations.py                  Migraciones versionadas e idempotentes (como ms-employees)
│       ├── notification_repository.py     Implementación Postgres (dedup + consultas)
│       └── employee_directory_repository.py  Implementación Postgres del directorio local
├── config.py
├── logging_setup.py                 Logger JSON estructurado (equivalente a Pino)
└── main.py                          Raíz de composición (FastAPI + lifespan)
```

Los casos de uso dependen de protocolos (`DedupNotificationRepository`, `NotificationQueryRepository`,
`EmployeeDirectoryRepository`), no de `asyncpg` directamente. `main.py` construye las implementaciones
Postgres y conecta todo en el `lifespan` de FastAPI, igual que `server.ts` en `ms-employees` es la
raíz de composición de ese servicio.

### Directorio local de empleados

`vacaciones.programadas` no trae `nombre`/`email` en su payload (ver `event-catalog.md`), así que
este servicio no podría redactar "Sus vacaciones fueron confirmadas, &lt;nombre&gt;" sin esos datos.
Dos opciones: (a) consultar `empleados-service` por REST cuando llegue el evento, o (b) mantener una
réplica local mínima construida a partir de `empleado.creado`. Se eligió (b) — la misma decisión que
`vacaciones-service` tomará para validar existencia de empleados (documentada en su propio README) —
porque un servicio puramente reactivo no debería depender de que otro servicio esté disponible en el
momento de procesar un evento; el desacople es justamente el punto de usar eventos.

`empleados_directorio(empleado_id, nombre, apellido, email)` se actualiza (`UPSERT`) cada vez que se
procesa un `empleado.creado` nuevo. Si `vacaciones.programadas` llega para un `empleadoId` que no
está en el directorio (no debería pasar en operación normal, porque `vacaciones-service` ya validó
la existencia del empleado antes de publicar), se registra una advertencia y se omite la
notificación en vez de inventar un destinatario.

### Consumidor RabbitMQ y fan-out

`RabbitMqConsumer` declara el exchange `rhm.events` (topic, durable) de forma idempotente — no
depende de que `empleados-service` haya arrancado primero — y declara su propia cola
(`notificaciones.queue`, durable), enlazándola a los routing keys registrados con `.on(...)`. Esa
cola propia, separada de las de `perfiles-service` y `vacaciones-service`, es lo que produce el
fan-out: un mismo mensaje publicado una vez en el exchange llega a las tres colas.

A diferencia del broker en `ms-employees` (donde publicar eventos es una capacidad *best-effort*
porque el servicio tiene otra razón de ser), aquí RabbitMQ es una dependencia dura: si no logra
conectarse tras los reintentos configurados, el arranque falla. Consumir eventos es la única razón
de existir de este servicio.

### Deduplicación (obligatoria)

`PostgresNotificationRepository.save_if_new()` ejecuta, en una única transacción:

1. `INSERT INTO eventos_procesados (id) VALUES ($event_id) ON CONFLICT DO NOTHING RETURNING id`.
2. Si no devuelve fila (ya existía), no se hace nada más: se descarta el duplicado.
3. Si devuelve fila, se inserta la notificación.

Esto evita la condición de carrera que tendría un enfoque "verificar y luego insertar" en dos pasos
separados. El mensaje AMQP se confirma (`ack`) en ambos casos — duplicado o no — porque
`message.process()` de `aio-pika` hace `ack` automático al salir del bloque sin excepción.

**Verificación realizada:** se publicó manualmente el mismo mensaje dos veces (mismo `id`) usando
la API de administración de RabbitMQ (equivalente a repetirlo desde la UI). El log de la segunda
entrega mostró `"msg": "Duplicate event ignored"` y la tabla `notificaciones` mantuvo una sola fila
para ese empleado.

## Simulación de notificaciones

No se envía correo real. Se registra un log estructurado:

```json
{"level": "info", "time": "...", "service": "ms-notifications", "msg": "[NOTIFICACIÓN] Tipo: BIENVENIDA | Para: carlos.vega@empresa.com | Mensaje: \"Bienvenido Carlos Vega, tu cuenta ha sido creada exitosamente.\"", "eventId": "...", "empleadoId": "E903", "notificationId": "..."}
```

```bash
docker compose logs -f notificaciones-service
```

## Persistencia

Base de datos propia (`notifications_db`, PostgreSQL 17), sin relación con `employees_db` ni
`departments_db`. Dos migraciones versionadas e idempotentes:

1. `create_tables` — `notificaciones` (`id`, `tipo` con `CHECK` en
   `BIENVENIDA`/`DESVINCULACION`/`VACACIONES`, `destinatario`, `mensaje`, `fecha_envio`,
   `empleado_id`, con índice sobre `empleado_id`) y `eventos_procesados` (`id`, `procesado_en`), la
   tabla de deduplicación.
2. `create_employee_directory` — `empleados_directorio` (`empleado_id`, `nombre`, `apellido`,
   `email`, `actualizado_en`).

## Salud

```bash
curl -i http://localhost:8080/notificaciones  # vía API Gateway
docker exec notificaciones-service python -c "import urllib.request;print(urllib.request.urlopen('http://127.0.0.1:8080/health').read())"
```

`/health` responde el mismo envelope que el resto del ecosistema:
`{"success": true, "message": "Servicio disponible", "data": {"status": "UP"}}`.
