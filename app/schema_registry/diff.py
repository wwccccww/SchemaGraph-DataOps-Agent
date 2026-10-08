"""两个 Schema 快照之间的差异。"""

from __future__ import annotations

from dataclasses import dataclass

from app.schema_registry.snapshot import SchemaSnapshot


@dataclass(frozen=True)
class SchemaDiff:
    """结构化 Schema 变更。"""

    added_tables: tuple[str, ...]
    removed_tables: tuple[str, ...]
    changed_tables: tuple[str, ...]
    added_edges: tuple[str, ...]
    removed_edges: tuple[str, ...]

    @property
    def is_empty(self) -> bool:
        return not any(
            (
                self.added_tables,
                self.removed_tables,
                self.changed_tables,
                self.added_edges,
                self.removed_edges,
            )
        )


def _edge_signatures(snapshot: SchemaSnapshot) -> dict[str, str]:
    return {
        edge.constraint_name: (
            f"{edge.constraint_name}|{edge.source_table}|{edge.target_table}|"
            f"{','.join(edge.source_columns)}|{','.join(edge.target_columns)}|{edge.inferred}"
        )
        for edge in snapshot.edges
    }


def diff_snapshots(before: SchemaSnapshot, after: SchemaSnapshot) -> SchemaDiff:
    """比较同一 database/schema 下的两个快照。"""

    if before.database_id != after.database_id or before.schema_name != after.schema_name:
        raise ValueError("schema diff requires the same database_id and schema_name")
    before_tables = {document.table_name: document.content_hash for document in before.documents}
    after_tables = {document.table_name: document.content_hash for document in after.documents}
    added = tuple(sorted(name for name in after_tables if name not in before_tables))
    removed = tuple(sorted(name for name in before_tables if name not in after_tables))
    changed = tuple(
        sorted(
            name
            for name in before_tables.keys() & after_tables.keys()
            if before_tables[name] != after_tables[name]
        )
    )
    before_map = _edge_signatures(before)
    after_map = _edge_signatures(after)
    names = before_map.keys() | after_map.keys()
    added_edges_list: list[str] = []
    removed_edges_list: list[str] = []
    for name in sorted(names):
        left = before_map.get(name)
        right = after_map.get(name)
        if left is None and right is not None:
            added_edges_list.append(name)
        elif left is not None and right is None:
            removed_edges_list.append(name)
        elif left is not None and right is not None and left != right:
            removed_edges_list.append(name)
            added_edges_list.append(name)
    return SchemaDiff(
        added_tables=added,
        removed_tables=removed,
        changed_tables=changed,
        added_edges=tuple(added_edges_list),
        removed_edges=tuple(removed_edges_list),
    )
