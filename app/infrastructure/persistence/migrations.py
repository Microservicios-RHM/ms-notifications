import asyncpg

_ADVISORY_LOCK_ID = 913_402

MIGRATIONS: list[tuple[int, str, str]] = [
    (
        1,
        "create_tables",
        """
        CREATE TABLE eventos_procesados (
            id UUID PRIMARY KEY,
            procesado_en TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );

        CREATE TABLE notificaciones (
            id UUID PRIMARY KEY,
            tipo VARCHAR(20) NOT NULL
                CHECK (tipo IN ('BIENVENIDA', 'DESVINCULACION', 'VACACIONES')),
            destinatario VARCHAR(254) NOT NULL,
            mensaje TEXT NOT NULL,
            fecha_envio TIMESTAMPTZ NOT NULL,
            empleado_id VARCHAR(50) NOT NULL
        );

        CREATE INDEX notificaciones_empleado_id_idx ON notificaciones (empleado_id);
        """,
    ),
    (
        2,
        "create_employee_directory",
        """
        CREATE TABLE empleados_directorio (
            empleado_id VARCHAR(50) PRIMARY KEY,
            nombre VARCHAR(100) NOT NULL,
            apellido VARCHAR(100) NOT NULL,
            email VARCHAR(254) NOT NULL,
            actualizado_en TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        """,
    ),
]


async def run_migrations(pool: asyncpg.Pool) -> list[str]:
    """Espejo de migration.runner.ts en ms-employees: versionadas, idempotentes, con
    advisory lock para evitar condiciones de carrera si el proceso arranca dos veces.
    """
    applied: list[str] = []
    async with pool.acquire() as conn:
        await conn.execute("SELECT pg_advisory_lock($1)", _ADVISORY_LOCK_ID)
        try:
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    version INTEGER PRIMARY KEY,
                    name TEXT NOT NULL,
                    applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
                """
            )
            for version, name, sql in MIGRATIONS:
                already_applied = await conn.fetchval(
                    "SELECT 1 FROM schema_migrations WHERE version = $1", version
                )
                if already_applied:
                    continue
                async with conn.transaction():
                    await conn.execute(sql)
                    await conn.execute(
                        "INSERT INTO schema_migrations (version, name) VALUES ($1, $2)",
                        version,
                        name,
                    )
                applied.append(f"{version} - {name}")
        finally:
            await conn.execute("SELECT pg_advisory_unlock($1)", _ADVISORY_LOCK_ID)
    return applied
