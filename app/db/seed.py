"""把确定性电商数据装入 PostgreSQL，并在结束后执行 ANALYZE。"""

from __future__ import annotations

import asyncio
import logging
import re

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from app.db.ecommerce_schema import apply_ecommerce_schema, create_ecommerce_indexes
from app.db.engine import get_admin_engine
from app.db.initialize import initialize_database_with_retry
from app.db.seed_data import SEED, SeedDataset, build_dataset, digest_rows
from app.db.tables import TABLE_NAMES, TABLE_SPECS

logger = logging.getLogger(__name__)

_SEED_LOCK = "schemagraph.ecommerce_seed"
_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,62}$")


async def seed_ecommerce(dataset: SeedDataset | None = None, *, seed: int = SEED) -> str:
    """重建 12 表并返回数据库中的数据摘要。"""

    current = dataset if dataset is not None else build_dataset(seed)
    engine = get_admin_engine()
    async with engine.begin() as conn:
        await conn.execute(
            text("SELECT pg_advisory_xact_lock(hashtext(:key)::bigint)"),
            {"key": _SEED_LOCK},
        )
        await apply_ecommerce_schema(conn, indexes=False)
        await _copy_dataset(conn, current)
        await create_ecommerce_indexes(conn)
        await conn.execute(text(f"ANALYZE {', '.join(_ident(name) for name in TABLE_NAMES)}"))
        digest = await database_digest(conn)
    if digest != current.digest:
        raise RuntimeError("database digest does not match the generated dataset")
    logger.info("ecommerce seed digest %s", digest)
    return digest


async def database_digest(conn: AsyncConnection) -> str:
    """按主键顺序回读 12 表并计算摘要。"""

    rows: dict[str, tuple[tuple[object, ...], ...]] = {}
    for spec in TABLE_SPECS:
        columns = ", ".join(_ident(column) for column in spec.columns)
        statement = text(
            f"SELECT {columns} FROM {_ident(spec.name)} ORDER BY {_ident(spec.primary_key)}"
        )
        result = await conn.execute(statement)
        rows[spec.name] = tuple(tuple(row) for row in result.all())
    return digest_rows(rows)


async def _copy_dataset(conn: AsyncConnection, dataset: SeedDataset) -> None:
    raw = await conn.get_raw_connection()
    driver = raw.driver_connection
    if driver is None:
        raise RuntimeError("admin connection is not backed by asyncpg")
    for spec in TABLE_SPECS:
        await driver.copy_records_to_table(
            spec.name,
            records=dataset.rows[spec.name],
            columns=list(spec.columns),
            schema_name="public",
        )


def _ident(value: str) -> str:
    if _IDENTIFIER.fullmatch(value) is None:
        raise ValueError(f"invalid identifier: {value}")
    return value


def main() -> None:
    """提供 `python -m app.db.seed` 入口。"""

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
    asyncio.run(_main())


async def _main() -> None:
    await initialize_database_with_retry()
    await seed_ecommerce()


if __name__ == "__main__":
    main()
