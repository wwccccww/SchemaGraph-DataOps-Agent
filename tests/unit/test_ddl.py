"""基准 DDL 与目录契约保持一致。"""

from __future__ import annotations

import re

from app.db.ecommerce_schema import ecommerce_sql, split_ecommerce_sql
from app.db.tables import FOREIGN_KEYS, INDEX_NAMES, JUNCTION_TABLES, TABLE_NAMES


def test_ddl_contains_tables_comments_and_indexes() -> None:
    sql = ecommerce_sql()

    assert sql.count("CREATE TABLE") == len(TABLE_NAMES)
    assert sql.count("CREATE INDEX") == len(INDEX_NAMES)
    assert sql.count("COMMENT ON TABLE") == len(TABLE_NAMES)
    assert sql.count("COMMENT ON COLUMN") == 46
    for name in TABLE_NAMES:
        assert f"CREATE TABLE {name} " in sql
    for name in INDEX_NAMES:
        assert f"CREATE INDEX {name} " in sql
    for name in JUNCTION_TABLES:
        assert f"COMMENT ON TABLE {name} IS '" in sql
        assert "[Junction Table]" in sql


def test_ddl_foreign_keys_match_catalog_contract() -> None:
    found: set[tuple[str, str, str, str]] = set()
    current = ""
    for line in ecommerce_sql().splitlines():
        create = re.match(r"CREATE TABLE (t_[a-z_]+) \(", line)
        if create:
            current = create.group(1)
        match = re.search(
            r"^\s*([a-z_]+)\s+.+REFERENCES\s+(t_[a-z_]+)\(([a-z_]+)\)",
            line,
        )
        if match:
            found.add((current, match.group(1), match.group(2), match.group(3)))

    expected = {
        (item.source_table, item.source_column, item.target_table, item.target_column)
        for item in FOREIGN_KEYS
    }
    assert found == expected


def test_sql_splitter_keeps_indexes_separate() -> None:
    tables, indexes = split_ecommerce_sql()

    assert len(indexes) == len(INDEX_NAMES)
    assert all(statement.upper().startswith("CREATE INDEX") for statement in indexes)
    assert all(not statement.upper().startswith("CREATE INDEX") for statement in tables)
    assert sum("CREATE TABLE" in statement for statement in tables) == len(TABLE_NAMES)
