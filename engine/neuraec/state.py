from __future__ import annotations

import json
import os
import threading
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

import numpy as np

from neuraec.constants import ENCODER_DIM, HALF_LIFE_DAYS, M_MAX
from neuraec.ordinal import decay, remap_ranks
from neuraec.records import domain_of, utcnow

try:
    import fcntl
except ImportError:  # pragma: no cover
    fcntl = None

_locks_guard = threading.Lock()
_thread_locks: dict[str, threading.Lock] = {}
_depth_local = threading.local()

STRONG_SOURCES = ("corr", "manual", "replied")
CORR_SOURCES = ("corr", "manual")


def _parse_ts(ts: str | datetime) -> datetime:
    if isinstance(ts, datetime):
        return ts if ts.tzinfo is not None else ts.replace(tzinfo=timezone.utc)
    return datetime.fromisoformat(str(ts).replace("Z", "+00:00"))


def _fmt_ts(ts: datetime) -> str:
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return ts.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


class RankMass:
    """Per-rank weight with exact exponential decay, aggregable.

    mass is stored relative to ref_ts. Reading at `now` multiplies by decay(ref_ts, now).
    Adding at `now` first brings mass to `now`, then adds w.
    """

    def __init__(self, N: int, data: dict[str, Any] | None = None) -> None:
        self.N = int(N)
        self.mass = np.zeros(self.N, dtype=np.float64)
        self.ref_ts: datetime | None = None
        self.n = 0
        self.n_corr = 0
        self.last_rank: int | None = None
        if data:
            for k, v in (data.get("mass") or {}).items():
                r = int(k)
                if 0 <= r < self.N:
                    self.mass[r] = float(v)
            self.ref_ts = _parse_ts(data["ref_ts"]) if data.get("ref_ts") else None
            self.n = int(data.get("n") or 0)
            self.n_corr = int(data.get("n_corr") or 0)
            self.last_rank = data.get("last_rank")

    def to_dict(self) -> dict[str, Any]:
        return {
            "mass": {str(r): float(m) for r, m in enumerate(self.mass) if m > 0},
            "ref_ts": _fmt_ts(self.ref_ts) if self.ref_ts else None,
            "n": self.n,
            "n_corr": self.n_corr,
            "last_rank": self.last_rank,
        }

    def _advance(self, now: datetime) -> None:
        if self.ref_ts is None:
            self.ref_ts = now
            return
        if now > self.ref_ts:
            self.mass *= decay(self.ref_ts, now, HALF_LIFE_DAYS)
            self.ref_ts = now

    def add(self, rank: int, w: float, now: datetime, is_correction: bool = False) -> None:
        self._advance(now)
        r = min(max(int(rank), 0), self.N - 1)
        self.mass[r] += float(w)
        self.n += 1
        self.last_rank = r
        if is_correction:
            self.n_corr += 1

    def at(self, now: datetime) -> np.ndarray:
        if self.ref_ts is None:
            return self.mass.copy()
        return self.mass * decay(self.ref_ts, now, HALF_LIFE_DAYS)

def _thread_lock(key: str) -> threading.Lock:
    with _locks_guard:
        lock = _thread_locks.get(key)
        if lock is None:
            lock = threading.Lock()
            _thread_locks[key] = lock
        return lock


def _depths() -> dict[str, int]:
    depths = getattr(_depth_local, "n", None)
    if depths is None:
        depths = {}
        _depth_local.n = depths
    return depths


def _acquire_os_lock(path: Path):
    path.touch(exist_ok=True)
    fh = open(path, "a+b")
    try:
        if fcntl is not None:
            fcntl.flock(fh.fileno(), fcntl.LOCK_EX)
            return fh
        import msvcrt

        fh.seek(0, os.SEEK_END)
        if fh.tell() < 1:
            fh.write(b"\0")
            fh.flush()
        fh.seek(0)
        while True:
            try:
                msvcrt.locking(fh.fileno(), msvcrt.LK_NBLCK, 1)
                return fh
            except OSError:
                time.sleep(0.05)
    except Exception:
        fh.close()
        raise


def _release_os_lock(fh) -> None:
    try:
        if fcntl is not None:
            fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
        else:
            import msvcrt

            fh.seek(0)
            msvcrt.locking(fh.fileno(), msvcrt.LK_UNLCK, 1)
    finally:
        fh.close()


@contextmanager
def user_dir_lock(root: Path) -> Iterator[None]:
    """Exclusive lock on the user's directory. Re-entrant in the same thread.

    On Unix this uses flock. On Windows, where fcntl is missing, it uses msvcrt.locking.
    """
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    lock_path = root / ".lock"
    key = str(lock_path.resolve())
    depths = _depths()
    if depths.get(key, 0) > 0:
        depths[key] += 1
        try:
            yield
        finally:
            depths[key] -= 1
        return
    thread_lock = _thread_lock(key)
    thread_lock.acquire()
    fh = None
    try:
        fh = _acquire_os_lock(lock_path)
        depths[key] = 1
        try:
            yield
        finally:
            depths[key] = 0
    finally:
        if fh is not None:
            _release_os_lock(fh)
        thread_lock.release()


class UserState:
    """On-disk per-user state (§5.1)."""

    def __init__(
        self,
        root: Path,
        user_id: str,
        N: int,
        order: str = "desc",
        profile: dict[str, list[str]] | None = None,
        encoder_name: str = "fake-hash-384",
        encoder_dim: int = ENCODER_DIM,
        m_max: int = M_MAX,
    ) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.m_max = int(m_max)
        self.dim = int(encoder_dim)
        self._lock_path = self.root / ".lock"
        self._vectors: np.ndarray = np.zeros((0, self.dim), dtype=np.float32)
        self._items: list[dict[str, Any]] = []
        self._uid_index: dict[str, int] = {}
        self.senders: dict[str, RankMass] = {}
        self.replied_to: dict[str, int] = {}
        if (self.root / "state.json").exists():
            self._load()
        else:
            self.user_id = user_id
            self.N = int(N)
            self.order = order
            self.profile = profile or {"fig": [], "fun": [], "set": []}
            self.rank_mass = RankMass(self.N)
            self.n_corr = 0
            self.n_conf = 0
            self.n_pred = 0
            self.created_at = _fmt_ts(utcnow())
            self.last_nightly_at = None
            self.initialized_at = None
            self.encoder_name = encoder_name
            self.encoder_dim = encoder_dim
            self.save()

    # ------------------------------------------------------------------ io
    def _load(self) -> None:
        meta = json.loads((self.root / "state.json").read_text(encoding="utf-8"))
        self.user_id = meta["user_id"]
        self.N = int(meta["N"])
        self.order = meta.get("order", "desc")
        self.profile = meta.get("profile") or {"fig": [], "fun": [], "set": []}
        self.rank_mass = RankMass(self.N, meta.get("rank_mass"))
        self.n_corr = int(meta.get("n_corr") or 0)
        self.n_conf = int(meta.get("n_conf") or 0)
        self.n_pred = int(meta.get("n_pred") or 0)
        self.created_at = meta.get("created_at")
        self.last_nightly_at = meta.get("last_nightly_at")
        self.initialized_at = meta.get("initialized_at")
        enc = meta.get("encoder") or {}
        self.encoder_name = enc.get("name", "fake-hash-384")
        self.encoder_dim = int(enc.get("dim") or ENCODER_DIM)
        self.dim = self.encoder_dim
        npy = self.root / "memory.npy"
        self._vectors = np.load(npy).astype(np.float32) if npy.exists() else np.zeros((0, self.dim), dtype=np.float32)
        items: list[dict[str, Any]] = []
        jsonl = self.root / "memory.jsonl"
        if jsonl.exists():
            for line in jsonl.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    items.append(json.loads(line))
        n = min(len(items), len(self._vectors))
        self._items = items[:n]
        self._vectors = self._vectors[:n]
        self._uid_index = {it["uid"]: i for i, it in enumerate(self._items)}
        senders_path = self.root / "senders.json"
        raw = json.loads(senders_path.read_text(encoding="utf-8")) if senders_path.exists() else {}
        self.senders = {k: RankMass(self.N, v) for k, v in raw.items()}
        replied_path = self.root / "replied.json"
        self.replied_to = json.loads(replied_path.read_text(encoding="utf-8")) if replied_path.exists() else {}

    def save(self) -> None:
        meta = {
            "user_id": self.user_id,
            "N": self.N,
            "order": self.order,
            "profile": self.profile,
            "rank_mass": self.rank_mass.to_dict(),
            "n_corr": self.n_corr,
            "n_conf": self.n_conf,
            "n_pred": self.n_pred,
            "created_at": self.created_at,
            "last_nightly_at": self.last_nightly_at,
            "initialized_at": self.initialized_at,
            "encoder": {"name": self.encoder_name, "dim": self.encoder_dim},
        }
        (self.root / "state.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
        np.save(self.root / "memory.npy", self._vectors)
        with open(self.root / "memory.jsonl", "w", encoding="utf-8") as f:
            for item in self._items:
                f.write(json.dumps(item, ensure_ascii=False) + "\n")
        (self.root / "senders.json").write_text(
            json.dumps({k: v.to_dict() for k, v in self.senders.items()}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        (self.root / "replied.json").write_text(json.dumps(self.replied_to, ensure_ascii=False, indent=2), encoding="utf-8")

    @contextmanager
    def lock(self) -> Iterator[None]:
        with user_dir_lock(self.root):
            yield

    # --------------------------------------------------------------- memory
    @property
    def size(self) -> int:
        return len(self._items)

    @property
    def vectors(self) -> np.ndarray:
        return self._vectors

    @property
    def items(self) -> list[dict[str, Any]]:
        return self._items

    def index_of_uid(self, uid: str) -> int | None:
        return self._uid_index.get(uid)

    def get(self, uid: str) -> dict[str, Any] | None:
        idx = self.index_of_uid(uid)
        return None if idx is None else self._items[idx]

    def conf_count_week(self, from_addr: str, now: datetime) -> int:
        count = 0
        for item in self._items:
            if item.get("from_addr") != from_addr or item.get("source") != "conf":
                continue
            if (now - _parse_ts(item["ts"])).total_seconds() <= 7 * 86400:
                count += 1
        return count

    def upsert_exemplar(
        self,
        *,
        uid: str,
        e: np.ndarray,
        message_id: str,
        thread_key: str,
        from_addr: str,
        rank: int,
        source: str,
        weight: float,
        s: list[float],
        r: list[float],
        ts: datetime,
        subject: str = "",
        snippet: str = "",
    ) -> None:
        e = np.asarray(e, dtype=np.float32).reshape(-1)
        if e.shape[0] != self.dim:
            raise ValueError(f"embedding dim {e.shape[0]} != {self.dim}")
        item = {
            "uid": uid,
            "message_id": message_id,
            "thread_key": thread_key,
            "from_addr": from_addr,
            "domain": domain_of(from_addr),
            "rank": int(rank),
            "source": source,
            "weight": float(weight),
            "s": [float(x) for x in s],
            "r": [float(x) for x in r],
            "ts": _fmt_ts(ts),
            "subject": subject,
            "snippet": snippet,
        }
        idx = self.index_of_uid(uid)
        if idx is not None:
            self._items[idx] = item
            self._vectors[idx] = e
            return
        if self.size >= self.m_max:
            self._evict(now=ts)
        self._items.append(item)
        self._uid_index[uid] = len(self._items) - 1
        if self._vectors.shape[0] == 0:
            self._vectors = e.reshape(1, -1)
        else:
            self._vectors = np.vstack([self._vectors, e.reshape(1, -1)])

    def _evict(self, now: datetime) -> None:
        if self.size == 0:
            return
        counts: dict[str, int] = {}
        for item in self._items:
            counts[item["from_addr"]] = counts.get(item["from_addr"], 0) + 1
        scores = [
            float(it.get("weight") or 0.0) * decay(it["ts"], now, HALF_LIFE_DAYS) for it in self._items
        ]
        candidates = [i for i, it in enumerate(self._items) if counts.get(it["from_addr"], 0) > 1]
        if not candidates:
            candidates = list(range(self.size))
        best_i = min(candidates, key=lambda i: scores[i])
        del self._items[best_i]
        self._vectors = np.delete(self._vectors, best_i, axis=0)
        self._uid_index = {it["uid"]: i for i, it in enumerate(self._items)}

    def strong_exemplars(self) -> list[tuple[int, dict[str, Any]]]:
        return [(i, it) for i, it in enumerate(self._items) if it.get("source") in STRONG_SOURCES]

    # --------------------------------------------------------------- masses
    def add_rank_mass(
        self,
        from_addr: str,
        rank: int,
        weight: float,
        ts: datetime,
        *,
        source: str,
    ) -> None:
        is_corr = source in CORR_SOURCES
        keys = [f"addr:{from_addr}"]
        dom = domain_of(from_addr)
        if dom:
            keys.append(f"dom:{dom}")
        for key in keys:
            rm = self.senders.get(key)
            if rm is None:
                rm = self.senders[key] = RankMass(self.N)
            rm.add(rank, weight, ts, is_correction=is_corr)
        if source in STRONG_SOURCES:
            self.rank_mass.add(rank, weight, ts, is_correction=is_corr)

    def sender_mass(self, from_addr: str, now: datetime) -> np.ndarray | None:
        rm = self.senders.get(f"addr:{from_addr}")
        return None if rm is None else rm.at(now)

    def domain_mass(self, domain: str, now: datetime) -> np.ndarray | None:
        if not domain:
            return None
        rm = self.senders.get(f"dom:{domain}")
        return None if rm is None else rm.at(now)

    def bump_replied(self, from_addr: str) -> None:
        if from_addr:
            self.replied_to[from_addr] = int(self.replied_to.get(from_addr) or 0) + 1

    def rebuild_masses(self) -> None:
        """Rebuild sender/domain/global masses from the exemplars (after remap)."""
        self.senders = {}
        self.rank_mass = RankMass(self.N)
        for item in sorted(self._items, key=lambda it: it["ts"]):
            self.add_rank_mass(
                item["from_addr"],
                int(item["rank"]),
                float(item.get("weight") or 0.0),
                _parse_ts(item["ts"]),
                source=item.get("source") or "corr",
            )

    def remap_to_n(self, N_new: int) -> None:
        old = [int(it["rank"]) for it in self._items]
        new = remap_ranks(old, self.N, N_new)
        for item, r in zip(self._items, new):
            item["rank"] = int(r)
        self.N = int(N_new)
        self.rebuild_masses()
