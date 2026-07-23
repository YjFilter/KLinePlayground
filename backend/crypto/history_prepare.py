from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from threading import Event, RLock, Thread
from typing import Any, Callable
from uuid import uuid4


class CryptoHistoryPrepareError(RuntimeError):
    pass


@dataclass
class _PrepareJob:
    job_id: str
    user: str
    payload: dict[str, Any]
    created_at: datetime
    expires_at: datetime
    status: str = "queued"
    completed_chunks: int = 0
    total_chunks: int = 0
    current_start: str | None = None
    current_end: str | None = None
    error: str | None = None
    result: dict[str, Any] | None = None
    cancel_event: Event = field(default_factory=Event)


class CryptoHistoryPrepareManager:
    def __init__(
        self,
        worker: Callable,
        *,
        runner: Callable[[Callable[[], None]], Any] | None = None,
        ttl_seconds: int = 1800,
        now: Callable[[], datetime] | None = None,
    ):
        self.worker = worker
        self.runner = runner or self._thread_runner
        self.ttl_seconds = int(ttl_seconds)
        self.now = now or (lambda: datetime.now(timezone.utc))
        self._jobs: dict[str, _PrepareJob] = {}
        self._lock = RLock()

    @staticmethod
    def _thread_runner(callback):
        thread = Thread(target=callback, name="crypto-history-prepare", daemon=True)
        thread.start()
        return thread

    def create(self, user: str, payload: dict[str, Any]) -> dict[str, Any]:
        if not user:
            raise CryptoHistoryPrepareError("history prepare user is required")
        with self._lock:
            self._cleanup_locked()
            created_at = self.now()
            job = _PrepareJob(
                job_id=uuid4().hex,
                user=str(user),
                payload=dict(payload or {}),
                created_at=created_at,
                expires_at=created_at + timedelta(seconds=self.ttl_seconds),
            )
            self._jobs[job.job_id] = job
        self.runner(lambda: self._run(job.job_id))
        return self._public(job)

    def get(self, job_id: str, user: str) -> dict[str, Any]:
        with self._lock:
            job = self._get_locked(job_id, user)
            return self._public(job)

    def cancel(self, job_id: str, user: str) -> dict[str, Any]:
        with self._lock:
            job = self._get_locked(job_id, user)
            if job.status in {"queued", "downloading"}:
                job.cancel_event.set()
                job.status = "cancelled"
            return self._public(job)

    def consume(self, job_id: str, user: str) -> dict[str, Any]:
        with self._lock:
            job = self._get_locked(job_id, user)
            if job.status == "consumed":
                raise CryptoHistoryPrepareError("history prepare job already consumed")
            if job.status != "ready" or job.result is None:
                raise CryptoHistoryPrepareError(f"history prepare job is not ready: {job.status}")
            job.status = "consumed"
            return job.result

    def _get_locked(self, job_id: str, user: str) -> _PrepareJob:
        self._cleanup_locked()
        job = self._jobs.get(str(job_id))
        if job is None or job.user != str(user):
            raise CryptoHistoryPrepareError("history prepare job not found")
        return job

    def _cleanup_locked(self):
        current = self.now()
        expired = [job_id for job_id, job in self._jobs.items() if job.expires_at <= current]
        for job_id in expired:
            self._jobs.pop(job_id, None)

    def _run(self, job_id: str):
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None or job.cancel_event.is_set():
                return
            job.status = "downloading"

        def update(progress):
            with self._lock:
                current = self._jobs.get(job_id)
                if current is None or current.cancel_event.is_set():
                    return
                current.completed_chunks = int(progress.get("completed_chunks", current.completed_chunks) or 0)
                current.total_chunks = int(progress.get("total_chunks", current.total_chunks) or 0)
                current.current_start = progress.get("current_start")
                current.current_end = progress.get("current_end")

        try:
            result = self.worker(
                job.user,
                dict(job.payload),
                update,
                job.cancel_event.is_set,
            )
            with self._lock:
                current = self._jobs.get(job_id)
                if current is None:
                    return
                if current.cancel_event.is_set():
                    current.status = "cancelled"
                    return
                current.result = result
                current.status = "ready"
                if current.total_chunks:
                    current.completed_chunks = current.total_chunks
        except Exception as exc:
            with self._lock:
                current = self._jobs.get(job_id)
                if current is None:
                    return
                if current.cancel_event.is_set():
                    current.status = "cancelled"
                else:
                    current.status = "failed"
                    current.error = str(exc)

    @staticmethod
    def _public(job: _PrepareJob) -> dict[str, Any]:
        percent = 100 if job.status in {"ready", "consumed"} else 0
        if job.total_chunks:
            percent = min(100, int(job.completed_chunks * 100 / job.total_chunks))
        payload = {
            "job_id": job.job_id,
            "status": job.status,
            "completed_chunks": job.completed_chunks,
            "total_chunks": job.total_chunks,
            "percent": percent,
            "current_start": job.current_start,
            "current_end": job.current_end,
            "error": job.error,
        }
        if job.result and isinstance(job.result.get("summary"), dict):
            payload.update(job.result["summary"])
        return payload
