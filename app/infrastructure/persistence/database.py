import asyncio
import logging

import asyncpg


async def create_pool(
    dsn: str,
    max_attempts: int,
    retry_delay_ms: int,
    logger: logging.Logger,
    min_size: int = 1,
    max_size: int = 5,
) -> asyncpg.Pool:
    last_error: Exception | None = None
    for attempt in range(1, max_attempts + 1):
        try:
            return await asyncpg.create_pool(dsn, min_size=min_size, max_size=max_size)
        except Exception as error:  # noqa: BLE001
            last_error = error
            logger.warning(
                "PostgreSQL connection attempt failed",
                extra={"fields": {"attempt": attempt, "error": str(error)}},
            )
            if attempt < max_attempts:
                await asyncio.sleep((retry_delay_ms / 1000) * attempt)
    raise RuntimeError("No fue posible conectar a PostgreSQL") from last_error
