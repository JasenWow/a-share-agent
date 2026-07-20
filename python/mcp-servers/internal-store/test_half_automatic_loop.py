"""Tests for the half-automatic feedback loop tools (sub-project ❻).

Covers: register_factor_candidate, list_candidates, promote_factor, reject_factor.
"""

import json
import sqlite3
from pathlib import Path
from unittest.mock import patch

import pytest


@pytest.fixture
def temp_db(tmp_path):
    """Temp DB with factor_library table for half-automatic loop tests."""
    db_path = tmp_path / "cache" / "meta.db"
    db_path.parent.mkdir(parents=True)
    conn = sqlite3.connect(str(db_path))
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS factor_library (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            name          TEXT NOT NULL,
            expression    TEXT NOT NULL,
            hypothesis    TEXT,
            operators     TEXT NOT NULL,
            data_fields   TEXT NOT NULL,
            ic            REAL,
            icir          REAL,
            turnover      REAL,
            sharpe        REAL,
            max_drawdown  REAL,
            universe      TEXT,
            period        TEXT,
            walk_forward  TEXT,
            status        TEXT DEFAULT 'active',
            source_experiment_id INTEGER,
            created_at    TEXT DEFAULT (datetime('now'))
        );
    """
    )
    conn.commit()
    conn.close()
    return db_path


def _patch_db_path(db_path):
    """Patch the server module's DB_PATH to point at the temp db."""
    return patch("server.DB_PATH", db_path)


# =========== register_factor_candidate ===========


class TestRegisterFactorCandidate:
    def test_registers_as_candidate_not_active(self, temp_db):
        from server import register_factor_candidate

        with _patch_db_path(temp_db):
            result = register_factor_candidate(
                name="momentum_20d_v2",
                expression="close/ts_delay(close,20)-1",
                operators=["div", "sub", "ts_delay"],
                data_fields=["close"],
                hypothesis="20d momentum variant",
                ic=0.05,
                icir=0.7,
                turnover=0.4,
                sharpe=1.1,
                max_drawdown=-0.18,
                universe="csi300",
                period="2020-2024",
                confidence=0.8,
                rationale="Stable across 3 windows",
            )
        assert len(result) == 1
        row = result[0]
        assert row["status"] == "candidate"  # NOT 'active'
        assert row["name"] == "momentum_20d_v2"
        assert row["icir"] == 0.7

    def test_stores_confidence_and_rationale_in_walk_forward(self, temp_db):
        """confidence + rationale are packed into walk_forward JSON (no schema change)."""
        from server import register_factor_candidate

        with _patch_db_path(temp_db):
            result = register_factor_candidate(
                name="f1",
                expression="expr1",
                operators=["op1"],
                data_fields=["close"],
                hypothesis="h",
                confidence=0.65,
                rationale="Looks promising because X",
            )
        wf = json.loads(result[0]["walk_forward"])
        assert wf["confidence"] == 0.65
        assert "X" in wf["rationale"]

    def test_dedup_by_expression(self, temp_db):
        from server import register_factor_candidate

        with _patch_db_path(temp_db):
            r1 = register_factor_candidate(
                name="f1",
                expression="same_expr",
                operators=["op"],
                data_fields=["close"],
                hypothesis="h",
            )
            r2 = register_factor_candidate(
                name="f2",
                expression="same_expr",
                operators=["op"],
                data_fields=["close"],
                hypothesis="h",
            )
        assert r1[0]["status"] == "candidate"
        assert r2[0]["status"] == "duplicate"
        assert r2[0]["id"] == r1[0]["id"]


# =========== list_candidates ===========


class TestListCandidates:
    def test_returns_only_candidates(self, temp_db):
        from server import list_candidates
        from server import register_factor_candidate

        with _patch_db_path(temp_db):
            register_factor_candidate(
                name="cand1",
                expression="e1",
                operators=["op"],
                data_fields=["close"],
                hypothesis="h",
            )
            # Manually insert an active and a rejected row to verify filtering
            conn = sqlite3.connect(str(temp_db))
            conn.execute(
                "INSERT INTO factor_library (name, expression, operators, data_fields, status) "
                "VALUES ('active1', 'ea', 'op', 'close', 'active')"
            )
            conn.execute(
                "INSERT INTO factor_library (name, expression, operators, data_fields, status) "
                "VALUES ('rej1', 'er', 'op', 'close', 'rejected')"
            )
            conn.commit()
            conn.close()

            candidates = list_candidates()
        assert len(candidates) == 1
        assert candidates[0]["name"] == "cand1"
        assert candidates[0]["status"] == "candidate"

    def test_returns_empty_when_none(self, temp_db):
        from server import list_candidates

        with _patch_db_path(temp_db):
            candidates = list_candidates()
        assert candidates == []


# =========== promote_factor ===========


class TestPromoteFactor:
    def test_promotes_candidate_to_active(self, temp_db):
        from server import promote_factor
        from server import register_factor_candidate

        with _patch_db_path(temp_db):
            reg = register_factor_candidate(
                name="f1",
                expression="e1",
                operators=["op"],
                data_fields=["close"],
                hypothesis="h",
            )
            fid = reg[0]["id"]
            result = promote_factor(fid, reviewer="jasen", notes="looks good")
        assert result[0]["status"] == "active"
        assert result[0]["_promoted_by"] == "jasen"
        assert result[0]["_promotion_notes"] == "looks good"

    def test_rejects_promotion_of_non_candidate(self, temp_db):
        from server import promote_factor

        with _patch_db_path(temp_db):
            # Insert an already-active factor
            conn = sqlite3.connect(str(temp_db))
            conn.execute(
                "INSERT INTO factor_library (name, expression, operators, data_fields, status) "
                "VALUES ('active1', 'ea', 'op', 'close', 'active')"
            )
            conn.commit()
            conn.close()

            result = promote_factor(1)
        assert "error" in result[0]
        assert "not 'candidate'" in result[0]["error"]

    def test_returns_error_for_unknown_id(self, temp_db):
        from server import promote_factor

        with _patch_db_path(temp_db):
            result = promote_factor(99999)
        assert "error" in result[0]
        assert "not found" in result[0]["error"]


# =========== reject_factor ===========


class TestRejectFactor:
    def test_rejects_candidate(self, temp_db):
        from server import register_factor_candidate, reject_factor

        with _patch_db_path(temp_db):
            reg = register_factor_candidate(
                name="f1",
                expression="e1",
                operators=["op"],
                data_fields=["close"],
                hypothesis="h",
            )
            fid = reg[0]["id"]
            result = reject_factor(fid, reason="IC too low", reviewer="jasen")
        assert result[0]["status"] == "rejected"
        assert result[0]["_rejected_by"] == "jasen"
        assert result[0]["_rejection_reason"] == "IC too low"

    def test_rejected_does_not_show_in_candidates(self, temp_db):
        from server import list_candidates, register_factor_candidate, reject_factor

        with _patch_db_path(temp_db):
            reg = register_factor_candidate(
                name="f1",
                expression="e1",
                operators=["op"],
                data_fields=["close"],
                hypothesis="h",
            )
            reject_factor(reg[0]["id"])
            candidates = list_candidates()
        assert candidates == []


# =========== end-to-end half-automatic loop ===========


class TestHalfAutomaticLoopE2E:
    def test_full_lifecycle_candidate_to_active(self, temp_db):
        """The core半自动 flow: agent registers candidate → human promotes."""
        from server import list_candidates, promote_factor, register_factor_candidate

        with _patch_db_path(temp_db):
            # 1. Agent registers a candidate (exploration)
            reg = register_factor_candidate(
                name="momentum_30d",
                expression="close/ts_delay(close,30)-1",
                operators=["div", "sub", "ts_delay"],
                data_fields=["close"],
                hypothesis="longer horizon momentum",
                ic=0.04,
                icir=0.55,
                confidence=0.7,
                rationale="Theoretical basis + stable IC",
            )
            assert reg[0]["status"] == "candidate"

            # 2. Human reviews via list_candidates
            pending = list_candidates()
            assert len(pending) == 1

            # 3. Human approves
            promoted = promote_factor(pending[0]["id"], reviewer="jasen")
            assert promoted[0]["status"] == "active"

            # 4. No more candidates pending
            assert list_candidates() == []
