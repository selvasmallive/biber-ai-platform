from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from uuid import uuid4

class JobStatus(str, Enum):
    queued = "queued"
    running = "running"
    completed = "completed"
    failed = "failed"
    preempted = "preempted"

@dataclass(order=True)
class Job:
    sort_index: tuple = field(init=False, repr=False)
    priority: int
    created_at: datetime
    job_id: str
    model: str
    task_type: str
    payload: dict
    status: JobStatus = JobStatus.queued
    gpu_required: bool = True

    def __post_init__(self):
        self.sort_index = (self.priority, self.created_at.timestamp())

class InMemoryScheduler:
    def __init__(self):
        self.jobs: list[Job] = []

    def submit(self, model: str, task_type: str, payload: dict, priority: int) -> Job:
        job = Job(
            priority=priority,
            created_at=datetime.utcnow(),
            job_id=f"job_{uuid4().hex[:12]}",
            model=model,
            task_type=task_type,
            payload=payload,
        )
        self.jobs.append(job)
        self.jobs.sort()
        return job

    def list_jobs(self):
        return self.jobs

    def next_job(self):
        for job in self.jobs:
            if job.status == JobStatus.queued:
                return job
        return None

scheduler = InMemoryScheduler()
