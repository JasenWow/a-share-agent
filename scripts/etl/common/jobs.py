"""JobService 任务队列：Protocol 抽象 + DuckDB 实现。

未来要升级到 pgboss 时，新增 PGBossJobService 实现同一 Protocol。
业务代码（runner / 未来外部消费者）只依赖 Protocol，不感知实现。

DuckDB 实现的适用场景：
- 日级 ETL、单研究员、任务数 <1000
- 单进程或多进程但低并发（<10 worker）
不适用：高并发多 worker 分布式场景（升级到 PGBossJobService）。
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Protocol

import duckdb


class JobStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class JobSpec:
    """提交任务的参数。"""

    domain: str
    params: dict
    max_attempts: int = 3


@dataclass
class Job:
    """任务实体。"""

    id: str
    domain: str
    params: dict
    status: JobStatus
    worker_id: str | None = None
    attempts: int = 0
    max_attempts: int = 3
    result: dict | None = None
    error: str | None = None
    created_at: str = ""
    claimed_at: str | None = None
    finished_at: str | None = None


class JobService(Protocol):
    """任务队列抽象接口。

    业务代码依赖此接口，不感知是 DuckDB 还是 pgboss 实现。
    """

    def submit(self, job: JobSpec) -> str: ...
    def claim(self, worker_id: str) -> Job | None: ...
    def complete(self, job_id: str, result: dict) -> None: ...
    def fail(self, job_id: str, error: str, retry: bool = True) -> None: ...
    def get(self, job_id: str) -> Job | None: ...
    def list_jobs(self, status: JobStatus | None = None, limit: int = 100) -> list[Job]: ...


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def init_jobs_table(conn: duckdb.DuckDBPyConnection) -> None:
    """建 etl_jobs 表 + 索引（幂等）。"""
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS etl_jobs (
            id              TEXT PRIMARY KEY,
            domain          TEXT NOT NULL,
            params_json     TEXT NOT NULL,
            status          TEXT NOT NULL,
            worker_id       TEXT,
            attempts        INTEGER DEFAULT 0,
            max_attempts    INTEGER DEFAULT 3,
            result_json     TEXT,
            error           TEXT,
            created_at      TEXT NOT NULL,
            claimed_at      TEXT,
            finished_at     TEXT
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_jobs_status ON etl_jobs(status, created_at)")


def _row_to_job(row, cols) -> Job:
    d = dict(zip(cols, row))
    return Job(
        id=d["id"],
        domain=d["domain"],
        params=json.loads(d["params_json"]),
        status=JobStatus(d["status"]),
        worker_id=d.get("worker_id"),
        attempts=d["attempts"],
        max_attempts=d["max_attempts"],
        result=json.loads(d["result_json"]) if d.get("result_json") else None,
        error=d.get("error"),
        created_at=d["created_at"],
        claimed_at=d.get("claimed_at"),
        finished_at=d.get("finished_at"),
    )


class DuckDBJobService:
    """DuckDB 实现：单连接内队列，事务保证 claim 不重复。"""

    def __init__(self, conn: duckdb.DuckDBPyConnection):
        self.conn = conn

    def submit(self, job: JobSpec) -> str:
        job_id = str(uuid.uuid4())
        self.conn.execute(
            """INSERT INTO etl_jobs
               (id, domain, params_json, status, attempts, max_attempts, created_at)
               VALUES (?, ?, ?, 'pending', 0, ?, ?)""",
            [job_id, job.domain, json.dumps(job.params), job.max_attempts, _now()],
        )
        return job_id

    def claim(self, worker_id: str) -> Job | None:
        """事务内领取一个 pending 任务，原子置为 running。"""
        # DuckDB 单连接事务内 SELECT+UPDATE 是原子的
        self.conn.execute("BEGIN TRANSACTION")
        try:
            row = self.conn.execute(
                """SELECT id FROM etl_jobs
                   WHERE status = 'pending'
                   ORDER BY created_at
                   LIMIT 1"""
            ).fetchone()
            if not row:
                self.conn.execute("ROLLBACK")
                return None
            job_id = row[0]
            now = _now()
            self.conn.execute(
                """UPDATE etl_jobs
                   SET status = 'running', worker_id = ?, claimed_at = ?,
                       attempts = attempts + 1
                   WHERE id = ? AND status = 'pending'""",
                [worker_id, now, job_id],
            )
            self.conn.execute("COMMIT")
            return self.get(job_id)
        except Exception:
            self.conn.execute("ROLLBACK")
            raise

    def complete(self, job_id: str, result: dict) -> None:
        self.conn.execute(
            """UPDATE etl_jobs
               SET status = 'completed', result_json = ?, finished_at = ?
               WHERE id = ?""",
            [json.dumps(result), _now(), job_id],
        )

    def fail(self, job_id: str, error: str, retry: bool = True) -> None:
        """失败处理：还能重试 → 回 PENDING；否则 → FAILED。"""
        job = self.get(job_id)
        if not job:
            return
        can_retry = retry and job.attempts < job.max_attempts
        if can_retry:
            self.conn.execute(
                "UPDATE etl_jobs SET status = 'pending', error = ? WHERE id = ?",
                [error, job_id],
            )
        else:
            self.conn.execute(
                """UPDATE etl_jobs
                   SET status = 'failed', error = ?, finished_at = ?
                   WHERE id = ?""",
                [error, _now(), job_id],
            )

    def get(self, job_id: str) -> Job | None:
        row = self.conn.execute("SELECT * FROM etl_jobs WHERE id = ?", [job_id]).fetchone()
        if not row:
            return None
        cols = [d[0] for d in self.conn.description]
        return _row_to_job(row, cols)

    def list_jobs(self, status: JobStatus | None = None, limit: int = 100) -> list[Job]:
        if status:
            rows = self.conn.execute(
                """SELECT * FROM etl_jobs WHERE status = ?
                   ORDER BY created_at DESC LIMIT ?""",
                [status.value, limit],
            ).fetchall()
        else:
            rows = self.conn.execute("SELECT * FROM etl_jobs ORDER BY created_at DESC LIMIT ?", [limit]).fetchall()
        cols = [d[0] for d in self.conn.description]
        return [_row_to_job(r, cols) for r in rows]
