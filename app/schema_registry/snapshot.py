"""不可变 Schema 快照。"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime

from app.schemas.catalog import SchemaEdge, TableDocument


def snapshot_fingerprint(
    documents: tuple[TableDocument, ...],
    edges: tuple[SchemaEdge, ...],
) -> str:
    """稳定摘要，用于判断 Schema 是否变化。"""

    table_payload = {
        document.table_name: document.content_hash for document in sorted(documents, key=lambda item: item.table_name)
    }
    edge_payload = [
        {
            "constraint_name": edge.constraint_name,
            "source": edge.source_table,
            "source_columns": edge.source_columns,
            "target": edge.target_table,
            "target_columns": edge.target_columns,
            "inferred": edge.inferred,
        }
        for edge in sorted(edges, key=lambda item: (item.constraint_name, item.source_table, item.target_table))
    ]
    raw = json.dumps(
        {"edges": edge_payload, "tables": table_payload},
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    return "sha256:" + hashlib.sha256(raw.encode()).hexdigest()


@dataclass(frozen=True)
class SchemaSnapshot:
    """某一时刻的目录视图。"""

    database_id: str
    schema_name: str
    fingerprint: str
    documents: tuple[TableDocument, ...]
    edges: tuple[SchemaEdge, ...]
    captured_at: datetime

    @classmethod
    def build(
        cls,
        *,
        database_id: str,
        schema_name: str,
        documents: tuple[TableDocument, ...],
        edges: tuple[SchemaEdge, ...],
        captured_at: datetime | None = None,
    ) -> SchemaSnapshot:
        moment = captured_at or datetime.now(tz=UTC)
        fingerprint = snapshot_fingerprint(documents, edges)
        return cls(
            database_id=database_id,
            schema_name=schema_name,
            fingerprint=fingerprint,
            documents=documents,
            edges=edges,
            captured_at=moment,
        )

    @property
    def version_id(self) -> str:
        """短版本 id，便于日志与 API。"""

        return self.fingerprint.removeprefix("sha256:")[:16]

    def table_names(self) -> frozenset[str]:
        return frozenset(document.table_name for document in self.documents)
