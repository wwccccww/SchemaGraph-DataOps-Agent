"""进程内 Schema 版本注册表。后续可换成持久化存储。"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime

from app.schema_registry.diff import SchemaDiff, diff_snapshots
from app.schema_registry.snapshot import SchemaSnapshot


@dataclass(frozen=True)
class ActivationAudit:
    database_id: str
    fingerprint: str
    activated_at: datetime
    forced: bool


@dataclass
class SchemaRegistry:
    """按 database_id 跟踪 staging / active 快照。"""

    _versions: dict[str, dict[str, SchemaSnapshot]] = field(default_factory=dict)
    _active: dict[str, str] = field(default_factory=dict)
    _staging: dict[str, str] = field(default_factory=dict)
    _audit: list[ActivationAudit] = field(default_factory=list)

    def _bucket(self, database_id: str) -> dict[str, SchemaSnapshot]:
        return self._versions.setdefault(database_id, {})

    def register(self, snapshot: SchemaSnapshot, *, activate: bool = False) -> SchemaDiff | None:
        """登记快照。若已有 active 且 fingerprint 不同，返回 diff。"""

        bucket = self._bucket(snapshot.database_id)
        bucket[snapshot.fingerprint] = snapshot
        diff: SchemaDiff | None = None
        active_fp = self._active.get(snapshot.database_id)
        if active_fp is not None and active_fp in bucket and active_fp != snapshot.fingerprint:
            diff = diff_snapshots(bucket[active_fp], snapshot)
        self._staging[snapshot.database_id] = snapshot.fingerprint
        if activate or active_fp is None:
            self._active[snapshot.database_id] = snapshot.fingerprint
            self._staging.pop(snapshot.database_id, None)
        return diff

    def activate(self, database_id: str, fingerprint: str, *, forced: bool = False) -> SchemaSnapshot:
        bucket = self._bucket(database_id)
        if fingerprint not in bucket:
            raise KeyError(f"unknown schema fingerprint for {database_id}")
        self._active[database_id] = fingerprint
        self._staging.pop(database_id, None)
        self._audit.append(
            ActivationAudit(
                database_id=database_id,
                fingerprint=fingerprint,
                activated_at=datetime.now(tz=UTC),
                forced=forced,
            )
        )
        return bucket[fingerprint]

    def activation_audit(self, database_id: str | None = None) -> tuple[ActivationAudit, ...]:
        if database_id is None:
            return tuple(self._audit)
        return tuple(item for item in self._audit if item.database_id == database_id)

    def active_snapshot(self, database_id: str) -> SchemaSnapshot | None:
        fingerprint = self._active.get(database_id)
        if fingerprint is None:
            return None
        return self._bucket(database_id).get(fingerprint)

    def staging_fingerprint(self, database_id: str) -> str | None:
        return self._staging.get(database_id)

    def get(self, database_id: str, fingerprint: str) -> SchemaSnapshot | None:
        return self._bucket(database_id).get(fingerprint)

    def database_ids(self) -> frozenset[str]:
        return frozenset(self._versions) | frozenset(self._active) | frozenset(self._staging)
