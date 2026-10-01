import asyncpg

from app.domain.repositories import EmployeeDirectoryRepository


class PostgresEmployeeDirectoryRepository(EmployeeDirectoryRepository):
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def upsert(self, empleado_id: str, nombre: str, apellido: str, email: str) -> None:
        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO empleados_directorio (empleado_id, nombre, apellido, email)
                VALUES ($1, $2, $3, $4)
                ON CONFLICT (empleado_id) DO UPDATE
                    SET nombre = EXCLUDED.nombre,
                        apellido = EXCLUDED.apellido,
                        email = EXCLUDED.email,
                        actualizado_en = NOW()
                """,
                empleado_id,
                nombre,
                apellido,
                email,
            )

    async def find(self, empleado_id: str) -> tuple[str, str, str] | None:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT email, nombre, apellido FROM empleados_directorio WHERE empleado_id = $1",
                empleado_id,
            )
        if row is None:
            return None
        return row["email"], row["nombre"], row["apellido"]
