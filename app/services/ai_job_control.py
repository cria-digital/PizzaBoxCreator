"""Cooperative cancellation for long-running AI pilot jobs."""

from __future__ import annotations

import threading

_jobs: dict[str, threading.Event] = {}
_lock = threading.Lock()


class AIJobCancelled(RuntimeError):
    """Raised when a running AI pilot job was cancelled by the user."""


def register_job(job_id: str) -> threading.Event:
    with _lock:
        event = threading.Event()
        _jobs[job_id] = event
        return event


def cancel_job(job_id: str) -> bool:
    with _lock:
        event = _jobs.get(job_id)
        if not event:
            return False
        event.set()
        return True


def finish_job(job_id: str) -> None:
    with _lock:
        _jobs.pop(job_id, None)


def is_cancelled(event: threading.Event) -> bool:
    return event.is_set()
