"""为单个慢 SQL 用例复制隔离数据库。管理角色负责建库，沙箱角色只测量。"""

from __future__ import annotations

import logging
import re
from collections.abc import Sequence

import sqlglot
from sqlalchemy import text
from sqlalchemy.engine import URL
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine, create_async_engine
from sqlglot import exp
from sqlglot.errors import SqlglotError

from app.config.settings import Settings
from app.db.ecommerce_schema import apply_ecommerce_schema, create_ecommerce_indexes
from app.db.tables import IDENTIFIER_PATTERN, TABLE_NAMES, TABLE_SPECS

logger = logging.getLogger(__name__)

SNAPSHOT_DATABASE = "slow_sql_snapshot"
_IDENTIFIER = re.compile(IDENTIFIER_PATTERN)
_RESERVED = frozenset({"postgres", "template0", "template1"})
_BATCH = 5000
_SANDBOX_ROLE = "sandbox_readonly"


def validate_index_precondition(sql: str) -> str:
    """只允许单条 DROP INDEX 或 CREATE INDEX，且索引表达式只能是标识符。"""

    statement = sql.strip()
    if statement == "" or "--" in statement or "/*" in statement:
        raise ValueError("index precondition must be one index statement")
    try:
        parsed = sqlglot.parse(
            statement,
            read="postgres",
            error_level=sqlglot.ErrorLevel.RAISE,
        )
        expressions = [item for item in parsed if item is not None]
    except SqlglotError as exc:
        raise ValueError("index precondition must be one index statement") from exc
    if len(expressions) != 1:
        raise ValueError("index precondition must be one index statement")
    expression = expressions[0]
    kind = str(expression.args.get("kind") or "").upper()
    if kind != "INDEX" or not isinstance(expression, exp.Create | exp.Drop):
        raise ValueError("index precondition must create or drop an index")
    if expression.args.get("concurrently") or expression.args.get("cascade"):
        raise ValueError("index precondition cannot use concurrently or cascade")
    for node in expression.walk():
        if isinstance(node, exp.Identifier) and _IDENTIFIER.fullmatch(node.name) is None:
            raise ValueError("index precondition identifiers are invalid")
        if isinstance(node, exp.Select | exp.Subquery | exp.Func | exp.Anonymous):
            raise ValueError("index precondition cannot contain queries or functions")
        if isinstance(node, exp.Add | exp.Sub | exp.Mul | exp.Div):
            raise ValueError("index precondition cannot contain queries or functions")
    return expression.sql(dialect="postgres")


def validate_database_name(name: str, *, current: str) -> str:
    """隔离库名必须是标识符，且不能是维护库或正在服务的业务库。"""

    if _IDENTIFIER.fullmatch(name) is None or name in _RESERVED or name == current:
        raise ValueError("database name is not allowed")
    return name


async def create_loaded_snapshot(settings: Settings) -> str:
    """从当前业务库复制一份无人连接的快照。不使用在线业务库做 TEMPLATE。"""

    name = validate_database_name(SNAPSHOT_DATABASE, current=settings.postgres_db)
    await drop_database(settings, name)
    try:
        await _create_database(settings, name)
        await _install_schema(settings, name)
        await _copy_tables(settings, name)
        await _finalize(settings, name, (), create_indexes=True)
    except Exception:
        await drop_database(settings, name)
        raise
    logger.info("created slow sql snapshot %s", name)
    return name


async def create_case_database(
    settings: Settings,
    name: str,
    *,
    snapshot: str,
    index_preconditions: Sequence[str],
) -> None:
    """从快照克隆用例库，并只在克隆上应用索引前置条件。"""

    target = validate_database_name(name, current=settings.postgres_db)
    source = validate_database_name(snapshot, current=settings.postgres_db)
    rendered = tuple(validate_index_precondition(item) for item in index_preconditions)
    await drop_database(settings, target)
    try:
        await _clone_database(settings, source, target)
        await _finalize(settings, target, rendered, create_indexes=False)
    except Exception:
        await drop_database(settings, target)
        raise


async def drop_database(settings: Settings, name: str) -> None:
    """丢弃隔离库。FORCE 只作用于这个名称，不碰业务库。"""

    target = validate_database_name(name, current=settings.postgres_db)
    maintenance = _engine(settings.admin_url().set(database="postgres"), autocommit=True)
    async with maintenance as engine, engine.connect() as conn:
        await conn.exec_driver_sql(f"DROP DATABASE IF EXISTS {target} WITH (FORCE)")


async def index_exists(
    settings: Settings,
    index_name: str,
    *,
    database: str | None = None,
) -> bool:
    """检查 public 中是否还有指定索引。索引名用参数传递。"""

    if _IDENTIFIER.fullmatch(index_name) is None:
        raise ValueError("index name is invalid")
    url = settings.admin_url()
    if database is not None:
        url = url.set(database=validate_database_name(database, current=settings.postgres_db))
    async with _engine(url) as engine, engine.connect() as conn:
        result = await conn.execute(
            text(
                "SELECT 1 FROM pg_catalog.pg_indexes "
                "WHERE schemaname = 'public' AND indexname = :name"
            ),
            {"name": index_name},
        )
        return result.first() is not None


async def _create_database(settings: Settings, name: str) -> None:
    maintenance = _engine(settings.admin_url().set(database="postgres"), autocommit=True)
    async with maintenance as engine, engine.connect() as conn:
        await conn.exec_driver_sql(f"CREATE DATABASE {name}")
        await conn.exec_driver_sql(f"GRANT CONNECT ON DATABASE {name} TO {_SANDBOX_ROLE}")


async def _clone_database(settings: Settings, source: str, target: str) -> None:
    maintenance = _engine(settings.admin_url().set(database="postgres"), autocommit=True)
    async with maintenance as engine, engine.connect() as conn:
        await conn.execute(
            text(
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                "WHERE datname = :name AND pid <> pg_backend_pid()"
            ),
            {"name": source},
        )
        await conn.exec_driver_sql(f"CREATE DATABASE {target} TEMPLATE {source}")
        await conn.exec_driver_sql(f"GRANT CONNECT ON DATABASE {target} TO {_SANDBOX_ROLE}")


async def _install_schema(settings: Settings, name: str) -> None:
    async with _engine(settings.admin_url().set(database=name)) as engine, engine.begin() as conn:
        await apply_ecommerce_schema(conn, indexes=False)
        await conn.exec_driver_sql(f"REVOKE TEMP ON DATABASE {name} FROM PUBLIC")
        await conn.exec_driver_sql("REVOKE CREATE ON SCHEMA public FROM PUBLIC")
        await conn.exec_driver_sql(f"GRANT USAGE ON SCHEMA public TO {_SANDBOX_ROLE}")


async def _copy_tables(settings: Settings, name: str) -> None:
    async with (
        _engine(settings.admin_url()) as source_pool,
        _engine(settings.admin_url().set(database=name)) as dest_pool,
        source_pool.connect() as source,
        dest_pool.begin() as dest,
    ):
        for spec in TABLE_SPECS:
            await _copy_table(source, dest, spec.name, spec.columns, spec.primary_key)


async def _copy_table(
    source: AsyncConnection,
    dest: AsyncConnection,
    table: str,
    columns: tuple[str, ...],
    primary_key: str,
) -> None:
    raw = await dest.get_raw_connection()
    driver = raw.driver_connection
    copy = getattr(driver, "copy_records_to_table", None)
    if copy is None:
        raise RuntimeError("admin connection is not backed by asyncpg")
    names = ", ".join(_ident(column) for column in columns)
    key = _ident(primary_key)
    relation = _ident(table)
    last: object | None = None
    while True:
        if last is None:
            statement = text(f"SELECT {names} FROM {relation} ORDER BY {key} LIMIT {_BATCH}")
            result = await source.execute(statement)
        else:
            statement = text(
                f"SELECT {names} FROM {relation} WHERE {key} > :last ORDER BY {key} LIMIT {_BATCH}"
            )
            result = await source.execute(statement, {"last": last})
        rows = [tuple(row) for row in result.all()]
        if not rows:
            return
        await copy(table, records=rows, columns=list(columns), schema_name="public")
        last = rows[-1][0]


async def _finalize(
    settings: Settings,
    name: str,
    index_preconditions: Sequence[str],
    *,
    create_indexes: bool,
) -> None:
    async with _engine(settings.admin_url().set(database=name)) as engine, engine.begin() as conn:
        if create_indexes:
            await create_ecommerce_indexes(conn)
        for statement in index_preconditions:
            await conn.exec_driver_sql(statement)
        tables = ", ".join(_ident(table) for table in TABLE_NAMES)
        await conn.exec_driver_sql(f"ANALYZE {tables}")


def _ident(value: str) -> str:
    if _IDENTIFIER.fullmatch(value) is None:
        raise ValueError("invalid identifier")
    return value


class _EngineContext:
    """关闭作用域时释放临时连接池。"""

    def __init__(self, url: URL, *, autocommit: bool = False) -> None:
        if autocommit:
            self._engine = create_async_engine(
                url,
                isolation_level="AUTOCOMMIT",
                pool_pre_ping=True,
                pool_size=1,
                max_overflow=0,
            )
        else:
            self._engine = create_async_engine(
                url,
                pool_pre_ping=True,
                pool_size=1,
                max_overflow=0,
            )

    async def __aenter__(self) -> AsyncEngine:
        return self._engine

    async def __aexit__(self, *_exc: object) -> None:
        await self._engine.dispose()


def _engine(url: URL, *, autocommit: bool = False) -> _EngineContext:
    return _EngineContext(url, autocommit=autocommit)
