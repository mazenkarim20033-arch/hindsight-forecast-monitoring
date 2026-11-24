"""An append-only log of decisions and what came of them, in one SQLite file on this computer.

Two protections, and one honest limit:
 * SQLite triggers refuse every UPDATE and DELETE, so the program itself cannot rewrite history, and ids never repeat (AUTOINCREMENT).
 * Every row stores the hash of the row before it (SHA-256 over the previous hash, time, kind, reference and the exact payload text), so
   `verify()` finds any later edit, removal or reordering, even by someone who bypassed the triggers.
 * The limit: this is tamper-*evident*, not tamper-proof. Anyone who can write the file can rebuild the whole chain. It shows that a log was
   altered; it cannot prove who wrote it, and it never leaves the computer.

Standard library only (sqlite3, hashlib, json)."""
import hashlib
import json
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path

GENESIS = "0" * 64
KINDS = ("decision", "outcome")

SCHEMA = """
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,
    kind TEXT NOT NULL CHECK (kind IN ('decision', 'outcome')),
    ref INTEGER,
    payload TEXT NOT NULL,
    prev_hash TEXT NOT NULL,
    hash TEXT NOT NULL UNIQUE
);
CREATE UNIQUE INDEX IF NOT EXISTS one_outcome_per_decision ON events(ref) WHERE kind = 'outcome';
CREATE TRIGGER IF NOT EXISTS events_no_update BEFORE UPDATE ON events BEGIN SELECT RAISE(ABORT, 'the audit log is append-only'); END;
CREATE TRIGGER IF NOT EXISTS events_no_delete BEFORE DELETE ON events BEGIN SELECT RAISE(ABORT, 'the audit log is append-only'); END;
"""


class AuditError(ValueError):
    def __init__(self, message: str, code: str, **params):
        super().__init__(message)
        self.code, self.params = code, params


def canonical(payload: dict) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def row_hash(prev: str, ts: str, kind: str, ref: int | None, payload_text: str) -> str:
    return hashlib.sha256("|".join([prev, ts, kind, "" if ref is None else str(ref), payload_text]).encode("utf-8")).hexdigest()


class AuditLog:
    """Opens (and creates) the file on first use, so importing the program touches no disk."""

    def __init__(self, path: Path):
        self.path = Path(path)
        self._lock = threading.RLock()
        self._db: sqlite3.Connection | None = None

    def _conn(self) -> sqlite3.Connection:
        if self._db is None:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self._db = sqlite3.connect(self.path, check_same_thread=False, isolation_level=None)
            self._db.row_factory = sqlite3.Row
            self._db.executescript(SCHEMA)
        return self._db

    def close(self) -> None:
        with self._lock:
            if self._db is not None:
                self._db.close()
                self._db = None

    @staticmethod
    def _event(r: sqlite3.Row) -> dict:
        return {"id": r["id"], "ts": r["ts"], "kind": r["kind"], "ref": r["ref"], "payload": json.loads(r["payload"]), "hash": r["hash"]}

    def append(self, kind: str, payload: dict, ref: int | None = None, ts: str | None = None) -> dict:
        if kind not in KINDS:
            raise AuditError(f"Unknown record kind {kind!r}.", "bad_kind")
        with self._lock:
            db = self._conn()
            if kind == "outcome":
                if ref is None or db.execute("SELECT 1 FROM events WHERE id = ? AND kind = 'decision'", (ref,)).fetchone() is None:
                    raise AuditError("That decision is not in the log.", "no_such_decision", id=ref)
                if db.execute("SELECT 1 FROM events WHERE kind = 'outcome' AND ref = ?", (ref,)).fetchone():
                    raise AuditError("An outcome is already recorded for this decision. The log does not allow it to be replaced.", "outcome_exists", id=ref)
            ts = ts or datetime.now(timezone.utc).isoformat(timespec="seconds")
            text = canonical(payload)
            db.execute("BEGIN IMMEDIATE")
            try:
                last = db.execute("SELECT hash FROM events ORDER BY id DESC LIMIT 1").fetchone()
                prev = last["hash"] if last else GENESIS
                h = row_hash(prev, ts, kind, ref, text)
                cur = db.execute("INSERT INTO events (ts, kind, ref, payload, prev_hash, hash) VALUES (?, ?, ?, ?, ?, ?)", (ts, kind, ref, text, prev, h))
                db.execute("COMMIT")
            except Exception:
                db.execute("ROLLBACK")
                raise
            return self.get(cur.lastrowid)

    def get(self, event_id: int) -> dict | None:
        with self._lock:
            r = self._conn().execute("SELECT * FROM events WHERE id = ?", (event_id,)).fetchone()
            return self._event(r) if r else None

    def events(self, kind: str | None = None, limit: int = 500) -> list[dict]:
        """Newest first."""
        with self._lock:
            q, args = "SELECT * FROM events" + (" WHERE kind = ?" if kind else "") + " ORDER BY id DESC LIMIT ?", ([kind] if kind else []) + [limit]
            return [self._event(r) for r in self._conn().execute(q, args)]

    def outcome_of(self, decision_id: int) -> dict | None:
        with self._lock:
            r = self._conn().execute("SELECT * FROM events WHERE kind = 'outcome' AND ref = ?", (decision_id,)).fetchone()
            return self._event(r) if r else None

    def verify(self) -> dict:
        """Walk the whole chain. `ok` is False at the first row whose stored hash or link does not match what its contents say."""
        with self._lock:
            prev, n = GENESIS, 0
            for r in self._conn().execute("SELECT * FROM events ORDER BY id"):
                n += 1
                if r["prev_hash"] != prev:
                    return {"ok": False, "n": n, "bad_id": r["id"], "reason": "link"}
                if row_hash(prev, r["ts"], r["kind"], r["ref"], r["payload"]) != r["hash"]:
                    return {"ok": False, "n": n, "bad_id": r["id"], "reason": "content"}
                prev = r["hash"]
            return {"ok": True, "n": n, "bad_id": None, "reason": None}
