from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass, asdict
from typing import Any, Dict, Optional


@dataclass
class JobRecord:
    job_id: str
    status: str
    message: str
    success: Optional[bool] = None
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class JobManager:
    def __init__(self):
        self._jobs: Dict[str, JobRecord] = {}
        self._lock = threading.Lock()

    def create_job(self, message: str = "Queued") -> JobRecord:
        job = JobRecord(job_id=str(uuid.uuid4()), status="queued", message=message)
        with self._lock:
            self._jobs[job.job_id] = job
        return job

    def update(self, job_id: str, *, status: Optional[str] = None, message: Optional[str] = None,
               success: Optional[bool] = None, result: Optional[Dict[str, Any]] = None,
               error: Optional[str] = None) -> Optional[JobRecord]:
        with self._lock:
            job = self._jobs.get(job_id)
            if not job:
                return None
            if status is not None:
                job.status = status
            if message is not None:
                job.message = message
            if success is not None:
                job.success = success
            if result is not None:
                job.result = result
            if error is not None:
                job.error = error
            return job

    def get(self, job_id: str) -> Optional[JobRecord]:
        with self._lock:
            return self._jobs.get(job_id)

    def as_dict(self, job_id: str) -> Optional[dict]:
        job = self.get(job_id)
        return asdict(job) if job else None


job_manager = JobManager()
