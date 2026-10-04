"""验证 sandbox_readonly 满足阶段 0 的最小权限要求。"""

from __future__ import annotations

import pytest
from app.db.engine import dispose_engines, get_admin_engine, get_sandbox_engine
from app.db.initialize import initialize_database
from pydantic import SecretStr
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

pytestmark = pytest.mark.integration


async def test_sandbox_role_has_no_elevated_privileges(database_settings) -> None:
    async with get_sandbox_engine().connect() as conn:
        read_only = await conn.scalar(
            text("SELECT current_setting('default_transaction_read_only')")
        )
        statement_timeout = await conn.scalar(text("SELECT current_setting('statement_timeout')"))
        lock_timeout = await conn.scalar(text("SELECT current_setting('lock_timeout')"))
        idle_timeout = await conn.scalar(
            text("SELECT current_setting('idle_in_transaction_session_timeout')")
        )
        selected = await conn.scalar(text("SELECT 1"))

    assert read_only == "on"
    assert statement_timeout == "5s"
    assert lock_timeout == "1s"
    assert idle_timeout == "2s"
    assert selected == 1

    async with get_admin_engine().connect() as conn:
        privileges = (
            await conn.execute(
                text(
                    """
                    SELECT
                      rolsuper,
                      rolcreatedb,
                      rolcreaterole,
                      rolcanlogin,
                      has_database_privilege(
                        'sandbox_readonly', current_database(), 'TEMP'
                      ) AS can_temp,
                      has_schema_privilege(
                        'sandbox_readonly', 'public', 'CREATE'
                      ) AS can_create,
                      (
                        SELECT count(*)
                        FROM pg_auth_members AS membership
                        JOIN pg_roles AS member_role
                          ON member_role.oid = membership.member
                        WHERE member_role.rolname = 'sandbox_readonly'
                      ) AS memberships
                    FROM pg_roles
                    WHERE rolname = 'sandbox_readonly'
                    """
                )
            )
        ).one()

    assert privileges.rolsuper is False
    assert privileges.rolcreatedb is False
    assert privileges.rolcreaterole is False
    assert privileges.rolcanlogin is True
    assert privileges.can_temp is False
    assert privileges.can_create is False
    assert privileges.memberships == 0


async def test_sandbox_role_cannot_create_table(database_settings) -> None:
    async with get_sandbox_engine().connect() as conn:
        with pytest.raises(DBAPIError) as caught:
            await conn.execute(text("CREATE TABLE phase0_forbidden (id INT)"))

    sqlstate = getattr(caught.value.orig, "sqlstate", None)
    assert sqlstate in {"25006", "42501"}


async def test_sandbox_password_is_quoted(database_settings) -> None:
    weird_password = "quote'\"\\;-- \npassword"
    updated = database_settings.model_copy(
        update={"sandbox_db_password": SecretStr(weird_password)}
    )
    engine = create_async_engine(updated.sandbox_url(), poolclass=NullPool)
    try:
        await initialize_database(updated)
        await dispose_engines()
        async with engine.connect() as conn:
            assert await conn.scalar(text("SELECT 1")) == 1
    finally:
        await engine.dispose()
        await initialize_database(database_settings)
        await dispose_engines()
