"""Tests for JobService (DuckDB implementation)."""
import duckdb
import pytest

from common.jobs import (
    DuckDBJobService,
    JobSpec,
    JobStatus,
    init_jobs_table,
)


@pytest.fixture()
def svc(tmp_path):
    db_path = tmp_path / "meta.db"
    conn = duckdb.connect(str(db_path))
    init_jobs_table(conn)
    yield DuckDBJobService(conn)
    conn.close()


def test_submit_returns_job_id(svc):
    """submit 返回 job_id（uuid 字符串）。"""
    job_id = svc.submit(JobSpec(domain="equity_daily", params={"date": "20260717"}))
    assert isinstance(job_id, str)
    assert len(job_id) > 0


def test_get_returns_job(svc):
    """get 返回 Job 对象，初始 PENDING。"""
    job_id = svc.submit(JobSpec(domain="equity_daily", params={"date": "20260717"}))
    job = svc.get(job_id)
    assert job is not None
    assert job.domain == "equity_daily"
    assert job.status == JobStatus.PENDING
    assert job.params == {"date": "20260717"}


def test_get_missing_returns_none(svc):
    """查不存在的 id 返回 None。"""
    assert svc.get("nonexistent-uuid") is None


def test_claim_returns_pending_job(svc):
    """claim 领取 pending 任务，状态变 RUNNING，attempts+1。"""
    job_id = svc.submit(JobSpec(domain="equity_daily", params={}))
    job = svc.claim("worker-1")
    assert job is not None
    assert job.id == job_id
    assert job.status == JobStatus.RUNNING
    assert job.worker_id == "worker-1"
    assert job.attempts == 1


def test_claim_returns_none_when_no_pending(svc):
    """无 pending 任务时返回 None。"""
    assert svc.claim("worker-1") is None


def test_claim_atomic_no_double_claim(svc):
    """两个 worker 不会领同一任务（事务保证）。"""
    svc.submit(JobSpec(domain="equity_daily", params={}))
    j1 = svc.claim("w1")
    j2 = svc.claim("w2")
    assert j1 is not None
    assert j2 is None


def test_claim_picks_oldest_first(svc):
    """claim 按创建时间排序，领最早的。"""
    import time
    id1 = svc.submit(JobSpec(domain="d1", params={}))
    time.sleep(0.01)  # 确保 created_at 不同
    id2 = svc.submit(JobSpec(domain="d2", params={}))
    claimed = svc.claim("w1")
    assert claimed.id == id1  # 最早的先领


def test_complete_sets_status_and_result(svc):
    """complete 置 COMPLETED 并写 result。"""
    job_id = svc.submit(JobSpec(domain="equity_daily", params={}))
    svc.claim("w1")
    svc.complete(job_id, {"status": "ok", "rows": 5000})
    job = svc.get(job_id)
    assert job.status == JobStatus.COMPLETED
    assert job.result == {"status": "ok", "rows": 5000}
    assert job.finished_at is not None


def test_fail_with_retry_back_to_pending(svc):
    """fail(retry=True) 且未达 max_attempts → 回到 PENDING。"""
    job_id = svc.submit(JobSpec(domain="equity_daily", params={}, max_attempts=3))
    svc.claim("w1")  # attempts=1
    svc.fail(job_id, "network error", retry=True)
    job = svc.get(job_id)
    assert job.status == JobStatus.PENDING
    assert "network error" in (job.error or "")


def test_fail_no_retry_sets_failed(svc):
    """fail(retry=False) → 直接 FAILED。"""
    job_id = svc.submit(JobSpec(domain="equity_daily", params={}, max_attempts=3))
    svc.claim("w1")
    svc.fail(job_id, "fatal", retry=False)
    job = svc.get(job_id)
    assert job.status == JobStatus.FAILED
    assert job.finished_at is not None


def test_fail_at_max_attempts_sets_failed(svc):
    """attempts >= max_attempts 时 fail(retry=True) 也置 FAILED。"""
    job_id = svc.submit(JobSpec(domain="equity_daily", params={}, max_attempts=1))
    svc.claim("w1")  # attempts=1, max=1
    svc.fail(job_id, "still failing", retry=True)
    job = svc.get(job_id)
    assert job.status == JobStatus.FAILED


def test_list_by_status(svc):
    """list 按 status 过滤。"""
    svc.submit(JobSpec(domain="d1", params={}))
    svc.submit(JobSpec(domain="d2", params={}))
    svc.claim("w1")  # 领走最早的一个 → RUNNING
    pending = svc.list_jobs(status=JobStatus.PENDING)
    running = svc.list_jobs(status=JobStatus.RUNNING)
    assert len(pending) == 1
    assert len(running) == 1


def test_list_all_when_no_status_filter(svc):
    """无 status 过滤返回全部。"""
    svc.submit(JobSpec(domain="d1", params={}))
    svc.submit(JobSpec(domain="d2", params={}))
    all_jobs = svc.list_jobs()
    assert len(all_jobs) == 2


def test_protocol_compliance():
    """DuckDBJobService 满足 JobService Protocol（结构化类型检查）。"""
    # Protocol 是结构化类型，运行时检查方法存在
    methods = ["submit", "claim", "complete", "fail", "get", "list_jobs"]
    for m in methods:
        assert hasattr(DuckDBJobService, m), f"missing method {m}"
