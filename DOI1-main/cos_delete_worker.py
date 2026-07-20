"""Background consumer for durable Tencent COS deletion tombstones.

The web process performs a best-effort drain after user-initiated deletes.  This
worker is the durable counterpart: it uses a dedicated database login/role and
continues processing tombstones even when the owning user never signs in again.
"""

from __future__ import annotations

from dataclasses import dataclass
import logging
import os
import re
import signal
import threading
from typing import Any, Protocol, Sequence

from research_store import ObjectStorage, TencentCosObjectStorage


LOGGER = logging.getLogger("cos_delete_worker")
_ROLE_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,62}$")


class WorkerConfigurationError(RuntimeError):
    """Raised when the worker is not configured safely."""


@dataclass(frozen=True)
class DeleteTask:
    id: int
    object_key: str
    attempts: int


@dataclass(frozen=True)
class WorkerSettings:
    database_url: str
    database_role: str = "research_cos_delete_worker"
    poll_seconds: int = 10
    batch_size: int = 100
    lease_seconds: int = 300
    retry_base_seconds: int = 30
    retry_max_seconds: int = 3600

    @classmethod
    def from_environment(cls) -> "WorkerSettings":
        database_url = os.getenv("COS_DELETE_WORKER_DATABASE_URL", "").strip()
        if not database_url:
            raise WorkerConfigurationError(
                "COS_DELETE_WORKER_DATABASE_URL must use the dedicated worker login."
            )
        role = os.getenv("COS_DELETE_WORKER_DB_ROLE", "research_cos_delete_worker").strip()
        if not _ROLE_NAME_RE.fullmatch(role):
            raise WorkerConfigurationError("COS_DELETE_WORKER_DB_ROLE is not a valid role name.")

        settings = cls(
            database_url=database_url,
            database_role=role,
            poll_seconds=_bounded_env_int("COS_DELETE_WORKER_POLL_SECONDS", 10, 1, 3600),
            batch_size=_bounded_env_int("COS_DELETE_WORKER_BATCH_SIZE", 100, 1, 500),
            lease_seconds=_bounded_env_int("COS_DELETE_WORKER_LEASE_SECONDS", 300, 30, 3600),
            retry_base_seconds=_bounded_env_int("COS_DELETE_WORKER_RETRY_BASE_SECONDS", 30, 1, 3600),
            retry_max_seconds=_bounded_env_int("COS_DELETE_WORKER_RETRY_MAX_SECONDS", 3600, 1, 86400),
        )
        if settings.retry_max_seconds < settings.retry_base_seconds:
            raise WorkerConfigurationError(
                "COS_DELETE_WORKER_RETRY_MAX_SECONDS must be at least the base retry interval."
            )
        return settings


def _bounded_env_int(name: str, default: int, minimum: int, maximum: int) -> int:
    raw = os.getenv(name, str(default)).strip()
    try:
        value = int(raw)
    except ValueError as exc:
        raise WorkerConfigurationError(f"{name} must be an integer.") from exc
    if not minimum <= value <= maximum:
        raise WorkerConfigurationError(f"{name} must be between {minimum} and {maximum}.")
    return value


class OutboxQueue(Protocol):
    def claim(self, *, limit: int, lease_seconds: int) -> Sequence[DeleteTask]: ...

    def mark_success(self, task_id: int) -> None: ...

    def mark_failure(self, task_id: int, *, error_type: str, retry_seconds: int) -> None: ...

    def close(self) -> None: ...


class PostgresOutboxQueue:
    """Cross-user queue access through a deliberately constrained BYPASSRLS role."""

    def __init__(self, database_url: str, database_role: str) -> None:
        if not _ROLE_NAME_RE.fullmatch(database_role):
            raise WorkerConfigurationError("Invalid database role name.")
        try:
            from psycopg import sql
            from psycopg_pool import ConnectionPool
        except ImportError as exc:  # pragma: no cover - dependency checked at image build
            raise WorkerConfigurationError("PostgreSQL worker dependencies are not installed.") from exc
        self._sql = sql
        self._role = database_role
        self._pool = ConnectionPool(
            conninfo=database_url,
            min_size=1,
            max_size=2,
            open=True,
            kwargs={"application_name": "research_cos_delete_worker"},
        )

    def _set_worker_role(self, connection: Any) -> None:
        # Identifier composition prevents an environment value becoming SQL.
        connection.execute(
            self._sql.SQL("SET LOCAL ROLE {}").format(self._sql.Identifier(self._role))
        )

    def claim(self, *, limit: int, lease_seconds: int) -> list[DeleteTask]:
        with self._pool.connection() as connection:
            with connection.transaction():
                self._set_worker_role(connection)
                cursor = connection.execute(
                    """WITH candidates AS (
                           SELECT id
                           FROM cos_delete_outbox
                           WHERE processed_at IS NULL
                             AND (claimed_until IS NULL OR claimed_until < now())
                           ORDER BY id
                           FOR UPDATE SKIP LOCKED
                           LIMIT %s
                       )
                       UPDATE cos_delete_outbox AS task
                       SET claimed_until = now() + make_interval(secs => %s),
                           attempts = attempts + 1
                       FROM candidates
                       WHERE task.id = candidates.id
                       RETURNING task.id, task.object_key, task.attempts""",
                    (max(1, min(int(limit), 500)), max(30, min(int(lease_seconds), 3600))),
                )
                return [DeleteTask(int(row[0]), str(row[1]), int(row[2])) for row in cursor.fetchall()]

    def mark_success(self, task_id: int) -> None:
        with self._pool.connection() as connection:
            with connection.transaction():
                self._set_worker_role(connection)
                connection.execute(
                    """UPDATE cos_delete_outbox
                       SET processed_at = now(), claimed_until = NULL, last_error = ''
                       WHERE id = %s AND processed_at IS NULL""",
                    (int(task_id),),
                )

    def mark_failure(self, task_id: int, *, error_type: str, retry_seconds: int) -> None:
        with self._pool.connection() as connection:
            with connection.transaction():
                self._set_worker_role(connection)
                connection.execute(
                    """UPDATE cos_delete_outbox
                       SET claimed_until = now() + make_interval(secs => %s),
                           last_error = %s
                       WHERE id = %s AND processed_at IS NULL""",
                    (
                        max(1, min(int(retry_seconds), 86400)),
                        str(error_type)[:200],
                        int(task_id),
                    ),
                )

    def close(self) -> None:
        self._pool.close()


@dataclass(frozen=True)
class BatchResult:
    claimed: int = 0
    completed: int = 0
    failed: int = 0
    queue_error: bool = False


class CosDeleteWorker:
    def __init__(
        self,
        queue: OutboxQueue,
        storage: ObjectStorage,
        settings: WorkerSettings,
        *,
        stop_event: threading.Event | None = None,
    ) -> None:
        self.queue = queue
        self.storage = storage
        self.settings = settings
        self.stop_event = stop_event or threading.Event()

    def _retry_seconds(self, attempts: int) -> int:
        exponent = max(0, min(int(attempts) - 1, 20))
        return min(
            self.settings.retry_max_seconds,
            self.settings.retry_base_seconds * (2**exponent),
        )

    def process_once(self) -> BatchResult:
        try:
            tasks = list(
                self.queue.claim(
                    limit=self.settings.batch_size,
                    lease_seconds=self.settings.lease_seconds,
                )
            )
        except Exception as exc:
            # Never emit the DSN, object key, or provider error message to logs.
            LOGGER.warning("outbox claim failed error_type=%s", type(exc).__name__)
            return BatchResult(queue_error=True)

        completed = 0
        failed = 0
        for task in tasks:
            if self.stop_event.is_set():
                # Unfinished claims become visible again after their lease expires.
                break
            try:
                self.storage.delete(task.object_key)
                self.queue.mark_success(task.id)
            except Exception as exc:
                failed += 1
                retry_seconds = self._retry_seconds(task.attempts)
                try:
                    self.queue.mark_failure(
                        task.id,
                        error_type=type(exc).__name__,
                        retry_seconds=retry_seconds,
                    )
                except Exception as mark_exc:
                    LOGGER.warning(
                        "outbox failure state update failed task_id=%s error_type=%s",
                        task.id,
                        type(mark_exc).__name__,
                    )
                LOGGER.warning(
                    "COS delete failed task_id=%s attempt=%s retry_seconds=%s error_type=%s",
                    task.id,
                    task.attempts,
                    retry_seconds,
                    type(exc).__name__,
                )
            else:
                completed += 1

        if tasks:
            LOGGER.info(
                "outbox batch claimed=%s completed=%s failed=%s",
                len(tasks),
                completed,
                failed,
            )
        return BatchResult(claimed=len(tasks), completed=completed, failed=failed)

    def run_forever(self) -> None:
        LOGGER.info("COS delete worker started")
        try:
            while not self.stop_event.is_set():
                result = self.process_once()
                # Drain a full queue promptly, but back off on an empty/error batch.
                if result.claimed >= self.settings.batch_size and not result.queue_error:
                    continue
                self.stop_event.wait(self.settings.poll_seconds)
        finally:
            self.queue.close()
            LOGGER.info("COS delete worker stopped")


def main() -> None:
    logging.basicConfig(
        level=os.getenv("COS_DELETE_WORKER_LOG_LEVEL", "INFO").upper(),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    settings = WorkerSettings.from_environment()
    stop_event = threading.Event()

    def request_stop(signum: int, _frame: Any) -> None:
        LOGGER.info("shutdown requested signal=%s", signum)
        stop_event.set()

    signal.signal(signal.SIGTERM, request_stop)
    signal.signal(signal.SIGINT, request_stop)

    queue = PostgresOutboxQueue(settings.database_url, settings.database_role)
    storage = TencentCosObjectStorage.from_environment()
    CosDeleteWorker(queue, storage, settings, stop_event=stop_event).run_forever()


if __name__ == "__main__":
    main()
