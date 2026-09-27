from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from neuraec.constants import OBSERVE_DELAY_HOURS, OPEN_EXPIRE_DAYS
from neuraec.records import utcnow


def _fmt(ts: datetime) -> str:
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return ts.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _parse(ts: str) -> datetime:
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


class Registry:
    """SQLite prediction log per mailbox (§5.2)."""

    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.path))
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._create()

    def close(self) -> None:
        self._conn.close()

    def _create(self) -> None:
        self._conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS predictions (
              uid            TEXT PRIMARY KEY,
              message_id     TEXT,
              thread_key     TEXT,
              from_addr      TEXT,
              received_at    TEXT,
              e_hash         TEXT,
              pred_rank      INTEGER,
              pred_u         REAL,
              pred_conf      REAL,
              stage          TEXT,
              model_version  TEXT,
              written_at     TEXT,
              written_label  TEXT,
              status         TEXT DEFAULT 'open',
              user_action    TEXT,
              final_rank     INTEGER,
              resolved_at    TEXT
            );
            CREATE INDEX IF NOT EXISTS ix_pred_status ON predictions(status, written_at);
            CREATE INDEX IF NOT EXISTS ix_pred_thread ON predictions(thread_key);
            """
        )
        self._conn.commit()

    def insert_prediction(
        self,
        *,
        uid: str,
        message_id: str,
        thread_key: str,
        from_addr: str,
        received_at: datetime,
        e_hash: str,
        pred_rank: int,
        pred_u: float,
        pred_conf: float,
        stage: str,
        model_version: str,
        written_label: str,
        written_at: datetime | None = None,
    ) -> bool:
        """Insert or replace. Returns False (no write) if the uid is frozen (§8.2)."""
        existing = self.get(uid)
        if existing is not None and existing.get("status") == "frozen":
            return False
        written_at = written_at or utcnow()
        self._conn.execute(
            """
            INSERT OR REPLACE INTO predictions (
              uid, message_id, thread_key, from_addr, received_at, e_hash,
              pred_rank, pred_u, pred_conf, stage, model_version,
              written_at, written_label, status, user_action, final_rank, resolved_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'open', NULL, NULL, NULL)
            """,
            (
                uid,
                message_id,
                thread_key,
                from_addr,
                _fmt(received_at),
                e_hash,
                int(pred_rank),
                float(pred_u),
                float(pred_conf),
                stage,
                model_version,
                _fmt(written_at),
                written_label,
            ),
        )
        self._conn.commit()
        return True

    def get(self, uid: str) -> dict[str, Any] | None:
        row = self._conn.execute("SELECT * FROM predictions WHERE uid = ?", (uid,)).fetchone()
        return dict(row) if row else None

    def lookup_thread(self, thread_key: str, exclude_uid: str | None = None) -> dict[str, Any] | None:
        """Prefer a resolved/frozen row with a user action; else the latest open row.

        exclude_uid: the email being classified must never see its own row.
        """
        if not thread_key:
            return None
        rows = self._conn.execute(
            "SELECT * FROM predictions WHERE thread_key = ? ORDER BY written_at DESC",
            (thread_key,),
        ).fetchall()
        if exclude_uid is not None:
            rows = [r for r in rows if r["uid"] != exclude_uid]
        if not rows:
            return None
        preferred_actions = {"moved", "replied", "manual"}
        for row in rows:
            d = dict(row)
            if d.get("status") in ("resolved", "frozen") and d.get("user_action") in preferred_actions:
                return d
        for row in rows:
            d = dict(row)
            if d.get("status") == "open":
                return d
        return dict(rows[0])

    def open_rows(self, *, older_than_hours: float | None = None, now: datetime | None = None) -> list[dict[str, Any]]:
        now = now or utcnow()
        rows = self._conn.execute("SELECT * FROM predictions WHERE status = 'open'").fetchall()
        out = [dict(r) for r in rows]
        if older_than_hours is None:
            return out
        cutoff = now - timedelta(hours=older_than_hours)
        return [r for r in out if _parse(r["written_at"]) < cutoff]

    def resolve(
        self,
        uid: str,
        *,
        user_action: str,
        final_rank: int | None,
        status: str,
        now: datetime | None = None,
    ) -> bool:
        """Idempotent: returns False if the row is already not open."""
        row = self.get(uid)
        if row is None:
            return False
        if row["status"] != "open":
            return False
        now = now or utcnow()
        self._conn.execute(
            """
            UPDATE predictions
               SET status = ?, user_action = ?, final_rank = ?, resolved_at = ?
             WHERE uid = ? AND status = 'open'
            """,
            (status, user_action, final_rank, _fmt(now), uid),
        )
        self._conn.commit()
        return True

    def note_written_label(self, uid: str, written_label: str) -> None:
        """Remember the folder name when the priority itself did not change."""
        self._conn.execute(
            """
            UPDATE predictions
               SET written_label = ?
             WHERE uid = ? AND status = 'open'
            """,
            (written_label, uid),
        )
        self._conn.commit()

    def expire_stale(self, now: datetime | None = None, days: int = OPEN_EXPIRE_DAYS) -> int:
        now = now or utcnow()
        cutoff = now - timedelta(days=days)
        n = 0
        for row in self.open_rows():
            if _parse(row["written_at"]) < cutoff:
                if self.resolve(row["uid"], user_action="none", final_rank=None, status="expired", now=now):
                    n += 1
        return n

    def rows(self) -> list[dict[str, Any]]:
        return [dict(r) for r in self._conn.execute("SELECT * FROM predictions").fetchall()]

    def expire_all_open(self, now: datetime | None = None) -> int:
        now = now or utcnow()
        n = 0
        for row in self.open_rows():
            if self.resolve(row["uid"], user_action="none", final_rank=None, status="expired", now=now):
                n += 1
        return n
