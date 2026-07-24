"""Eval runner REST API.

Runs as a separate Deployment (KEDA HTTP-scaled, min=0 max=2) in the same
namespace as the agentpod. Reads eval_cases.yaml and system.yaml from the
agent config PVC (written by agent-engine at deploy time). Results are
written to MongoDB so the agentpod /evals/results route can serve them.

Endpoints:
    POST /evals/run                Run all patterns
    POST /evals/run/{pattern}      Run one pattern (tool_use / hitl / structured_output / multi_agent)
    GET  /evals/status             Current run status
    GET  /evals/results            Latest run summary
    GET  /evals/results/{run_id}   Specific run summary
    GET  /health                   Liveness check
"""

from __future__ import annotations

import asyncio
import logging
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import boto3
import yaml
from fastapi import BackgroundTasks, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

# ── Configuration ─────────────────────────────────────────────────────────────

AGENT_URL = os.environ.get("AGENT_HOST", "http://localhost:5002")
EVAL_CASES_PATH = Path(
    os.environ.get("EVAL_CASES_PATH", "/agent-config/eval_cases.yaml")
)
EVAL_SYSTEM_CONFIG = Path(
    os.environ.get("EVAL_SYSTEM_CONFIG", "/agent-config/system.yaml")
)
EVAL_OUTPUT_DIR = Path(
    os.environ.get("EVAL_OUTPUT_DIR", tempfile.gettempdir() + "/eval_output")
)

AGENT_ORG = os.environ.get("AI_PLATFORM_AGENT_ORG", "default")
AGENT_NAME = os.environ.get("AI_PLATFORM_AGENT_NAME", "agent")


_HASH_EXTENSIONS = {".md", ".yaml", ".json"}
_HASH_EXCLUDE_DIRS = {"evals", "deployment"}


def _compute_config_hash(config_dir: str) -> str:
    """SHA256 of behavior-relevant config files (prompts, skills, runtime, tools)."""
    import hashlib
    from pathlib import Path

    h = hashlib.sha256()
    base = Path(config_dir)
    if base.exists():
        for fpath in sorted(base.rglob("*")):
            if not fpath.is_file():
                continue
            if fpath.suffix not in _HASH_EXTENSIONS:
                continue
            if any(
                part in _HASH_EXCLUDE_DIRS for part in fpath.relative_to(base).parts
            ):
                continue
            h.update(str(fpath.relative_to(base)).encode())
            h.update(fpath.read_bytes())
    return h.hexdigest()[:16]  # 16-char prefix is enough


_config_dir = os.environ.get("AGENT_CONFIG_DIR", "config/agent")
AGENT_CONFIG_HASH = os.environ.get("AGENT_CONFIG_HASH") or _compute_config_hash(
    _config_dir
)

AGENT_AUTH_TOKEN = os.environ.get("AGENT_AUTH_TOKEN", "")
ENABLE_AUTH = os.environ.get("ENABLE_AUTH", "false").lower() in ("true", "1")
EVAL_MAX_CONCURRENCY = int(os.environ.get("EVAL_MAX_CONCURRENCY", "3"))
EVAL_S3_BUCKET = os.environ.get("EVAL_S3_BUCKET", "")

ALL_PATTERNS = ["tool_use", "structured_output", "hitl", "multi_agent"]


# ── State ─────────────────────────────────────────────────────────────────────

_status: dict[str, Any] = {"state": "idle", "run_id": None}
_latest_result: dict[str, Any] | None = None
_run_lock = asyncio.Lock()


# ── Eval runner ───────────────────────────────────────────────────────────────


def _find_eval_files(pattern: str | None) -> list[Path]:
    """Return eval data file(s) for the given pattern from the PVC-mounted cases file."""
    if not EVAL_CASES_PATH.exists():
        raise FileNotFoundError(f"eval_cases.yaml not found at {EVAL_CASES_PATH}")

    if pattern is None:
        return [EVAL_CASES_PATH]

    # Filter by tag into a temp file
    cases = yaml.safe_load(EVAL_CASES_PATH.read_text()) or []
    filtered = [c for c in cases if c.get("tag") == pattern]
    if not filtered:
        raise FileNotFoundError(f"No cases with tag '{pattern}' in {EVAL_CASES_PATH}")
    tmp = tempfile.NamedTemporaryFile(
        mode="w", suffix=".yaml", prefix=f"eval_{pattern}_", delete=False
    )
    yaml.dump(filtered, tmp, default_flow_style=False, allow_unicode=True)
    tmp.close()
    return [Path(tmp.name)]


def _get_system_yaml_content() -> str:
    """Return system.yaml content with postgres credentials filled from env vars."""
    if not EVAL_SYSTEM_CONFIG.exists():
        raise FileNotFoundError(f"system.yaml not found at {EVAL_SYSTEM_CONFIG}")

    config = yaml.safe_load(EVAL_SYSTEM_CONFIG.read_text())

    for backend in config.get("storage", []):
        if backend.get("type") == "postgres":
            backend["host"] = os.environ.get(
                "POSTGRES_HOST", backend.get("host", "localhost")
            )
            backend["port"] = int(
                os.environ.get("POSTGRES_PORT", str(backend.get("port", 5432)))
            )
            backend["database"] = os.environ.get(
                "POSTGRES_DB", backend.get("database", "template_agent")
            )
            backend["user"] = os.environ.get(
                "POSTGRES_USER", backend.get("user", "postgres")
            )
            backend["password"] = os.environ.get(
                "POSTGRES_PASSWORD", backend.get("password", "")
            )

    return yaml.dump(config, default_flow_style=False, allow_unicode=True)


def _system_yaml_path() -> Path:
    """Write system.yaml with env-injected credentials to a temp file and return its path."""
    content = _get_system_yaml_content()
    tmp = tempfile.NamedTemporaryFile(
        mode="w", suffix=".yaml", prefix="eval_system_", delete=False
    )
    tmp.write(content)
    tmp.close()
    return Path(tmp.name)


def _run_eval_pattern_sync(
    eval_file: Path, system_yaml: Path, output_dir: Path, auth_token: str = ""
) -> int:
    """Blocking subprocess call — must be run in a thread pool, not the event loop."""
    runner = Path(__file__).parent / "run_eval.py"
    env = dict(os.environ)
    if auth_token:
        env["AGENT_AUTH_TOKEN"] = auth_token  # user session token for MCP tool calls
    result = subprocess.run(
        [
            sys.executable,
            str(runner),
            "--agent-url",
            AGENT_URL,
            "--eval-data",
            str(eval_file),
            "--system",
            str(system_yaml),
            "--output-dir",
            str(output_dir),
        ],
        check=False,
        env=env,
    )
    return result.returncode


async def _run_eval_pattern(
    eval_file: Path, system_yaml: Path, output_dir: Path, auth_token: str = ""
) -> int:
    """Run one eval pattern in a thread pool so the event loop stays responsive."""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(
        None, _run_eval_pattern_sync, eval_file, system_yaml, output_dir, auth_token
    )


def _upload_to_s3(local_dir: Path, run_id: str) -> str | None:
    """Upload result files to S3. Returns s3_prefix or None."""
    if not EVAL_S3_BUCKET:
        return None
    s3_prefix = f"evals/{AGENT_ORG}/{AGENT_NAME}/{AGENT_CONFIG_HASH}/{run_id}/"
    try:
        s3 = boto3.client("s3")
        for fpath in local_dir.iterdir():
            if fpath.is_file():
                s3.upload_file(str(fpath), EVAL_S3_BUCKET, f"{s3_prefix}{fpath.name}")
                log.info("Uploaded s3://%s/%s%s", EVAL_S3_BUCKET, s3_prefix, fpath.name)
        return s3_prefix
    except Exception as exc:
        log.error("S3 upload failed: %s", exc)
        return None


def _score_from_counts(passed: int, failed: int, errors: int) -> tuple[str, float]:
    total = passed + failed + errors
    if total == 0:
        return "error", 0.0
    score = round(passed / total, 3)
    if errors > 0 and passed == 0:
        status = "error"
    elif passed == total:
        status = "passed"
    else:
        status = "failed"
    return status, score


def _load_results_from_db(run_started_at: datetime) -> dict[str, Any]:
    """Load eval results from the evaluation_results PostgreSQL table.

    Finds the latest run_id written since run_started_at, fetches all rows for
    it, serialises them to JSON-safe dicts, and computes a summary. Returns a
    dict with 'turns' and 'summary' keys, or an empty dict if the query fails.
    """
    from collections import defaultdict

    try:
        import psycopg2
        import psycopg2.extras
    except ImportError as exc:
        log.warning("psycopg2 not available, skipping DB result load: %s", exc)
        return {}

    try:
        conn = psycopg2.connect(
            host=os.environ.get("POSTGRES_HOST", "localhost"),
            port=int(os.environ.get("POSTGRES_PORT", "5432")),
            dbname=os.environ.get("POSTGRES_DB", "template_agent"),
            user=os.environ.get("POSTGRES_USER", "postgres"),
            password=os.environ.get("POSTGRES_PASSWORD", "postgres"),
        )
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                # Find the latest run_id for rows written during this eval run
                cur.execute(
                    "SELECT run_id FROM evaluation_results "
                    "WHERE timestamp >= %s "
                    "ORDER BY timestamp DESC LIMIT 1",
                    (run_started_at,),
                )
                row = cur.fetchone()
                if row is None:
                    log.warning(
                        "No evaluation_results rows found since %s", run_started_at
                    )
                    return {}

                db_run_id = row["run_id"]
                log.info("Loading DB results for run_id=%s", db_run_id)

                cur.execute(
                    "SELECT * FROM evaluation_results WHERE run_id = %s",
                    (db_run_id,),
                )
                raw_rows = cur.fetchall()
        finally:
            conn.close()
    except Exception as exc:
        log.warning("Could not load eval results from DB: %s", exc)
        return {}

    # --- Compute summary from raw (typed) rows before serialisation ---
    overall_counts: dict[str, int] = {"PASS": 0, "FAIL": 0, "ERROR": 0}
    by_metric: dict[str, dict[str, Any]] = defaultdict(
        lambda: {"pass": 0, "fail": 0, "scores": []}
    )
    by_conversation: dict[str, dict[str, int]] = defaultdict(
        lambda: {"pass": 0, "fail": 0}
    )

    for r in raw_rows:
        result_val = str(r.get("result") or "").upper()
        if result_val not in overall_counts:
            result_val = "ERROR"
        overall_counts[result_val] += 1

        metric = str(r.get("metric_identifier") or "unknown")
        if result_val == "PASS":
            by_metric[metric]["pass"] += 1
        elif result_val == "FAIL":
            by_metric[metric]["fail"] += 1
        try:
            score = float(r.get("score") or 0)
            by_metric[metric]["scores"].append(score)
        except (TypeError, ValueError):
            pass

        conv_id = str(r.get("conversation_group_id") or "unknown")
        if result_val == "PASS":
            by_conversation[conv_id]["pass"] += 1
        elif result_val == "FAIL":
            by_conversation[conv_id]["fail"] += 1

    total = len(raw_rows)
    overall_with_rates: dict[str, Any] = dict(overall_counts)
    overall_with_rates["pass_rate"] = (
        round(overall_counts["PASS"] / total, 3) if total else 0.0
    )
    overall_with_rates["fail_rate"] = (
        round(overall_counts["FAIL"] / total, 3) if total else 0.0
    )
    overall_with_rates["error_rate"] = (
        round(overall_counts["ERROR"] / total, 3) if total else 0.0
    )

    by_metric_out: dict[str, Any] = {}
    for metric, data in by_metric.items():
        m_total = data["pass"] + data["fail"]
        scores = data["scores"]
        by_metric_out[metric] = {
            "pass": data["pass"],
            "fail": data["fail"],
            "pass_rate": round(data["pass"] / m_total, 3) if m_total else 0.0,
            "score_mean": round(sum(scores) / len(scores), 3) if scores else 0.0,
        }

    summary: dict[str, Any] = {
        "total_evaluations": total,
        "summary_stats": {
            "overall": overall_with_rates,
            "by_metric": by_metric_out,
            "by_conversation": {k: dict(v) for k, v in by_conversation.items()},
        },
    }

    # --- Serialise rows to JSON-safe dicts ---
    turns: list[dict[str, Any]] = []
    for r in raw_rows:
        turn: dict[str, Any] = {}
        for k, v in r.items():
            if isinstance(v, datetime):
                turn[k] = v.isoformat()
            elif isinstance(v, float):
                turn[k] = str(v)
            else:
                turn[k] = v
        turns.append(turn)

    return {"turns": turns, "summary": summary, "ls_run_id": db_run_id}


async def _run_eval(
    pattern: str | None,
    config_hash: str | None = None,
    org: str | None = None,
    name: str | None = None,
    auth_token: str = "",
) -> None:
    """Core eval runner — invoked in background."""
    global _latest_result

    run_id = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    _status.update({"state": "running", "run_id": run_id})
    log.info("Eval run started: run_id=%s pattern=%s", run_id, pattern or "all")

    tmp_files: list[Path] = []
    try:
        system_yaml = _system_yaml_path()
        eval_files = _find_eval_files(pattern)
        # Track temp files created by _find_eval_files (tag-filtered) for cleanup
        tmp_files = [f for f in eval_files if f.parent != EVAL_CASES_PATH.parent]
    except FileNotFoundError as exc:
        log.error("%s", exc)
        _status.update({"state": "error", "run_id": run_id})
        return

    EVAL_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    run_output = EVAL_OUTPUT_DIR / run_id
    run_output.mkdir(parents=True, exist_ok=True)

    sem = asyncio.Semaphore(EVAL_MAX_CONCURRENCY)

    async def _run_one(eval_file: Path) -> int:
        async with sem:
            log.info("Running %s", eval_file.name)
            rc = await _run_eval_pattern(eval_file, system_yaml, run_output, auth_token)
            log.info("%s → exit code %d", eval_file.name, rc)
            return rc

    run_started_at = datetime.now(timezone.utc)
    try:
        await asyncio.gather(*[_run_one(f) for f in eval_files])
    finally:
        for tmp in tmp_files:
            tmp.unlink(missing_ok=True)
        # Clean up the injected system.yaml temp file
        if "system_yaml" in locals():
            try:
                system_yaml.unlink(missing_ok=True)
            except Exception:
                pass

    total_pass, total_fail, total_error = 0, 0, 0
    eval_status, eval_score = _score_from_counts(total_pass, total_fail, total_error)

    s3_prefix = _upload_to_s3(run_output, run_id)
    s3_url = f"s3://{EVAL_S3_BUCKET}/{s3_prefix}summary.json" if s3_prefix else None

    result: dict[str, Any] = {
        "run_id": run_id,
        "org": AGENT_ORG,
        "name": AGENT_NAME,
        "config_hash": AGENT_CONFIG_HASH,
        "eval_status": eval_status,
        "eval_score": eval_score,
        "pass": total_pass,
        "fail": total_fail,
        "error": total_error,
        "output_dir": str(run_output),
        "s3_url": s3_url,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    _latest_result = result
    _status.update({"state": "completed", "run_id": run_id})
    log.info("Eval complete: status=%s score=%.3f", eval_status, eval_score)

    # Build rich results_detail from the evaluation_results PostgreSQL table
    results_detail = dict(result)
    db_data = await asyncio.get_running_loop().run_in_executor(
        None, _load_results_from_db, run_started_at
    )
    results_detail.update(db_data)

    # Recompute scalars from DB summary — file storage was removed so
    # _aggregate_summaries() returned zeros; DB summary has the real counts.
    overall = (
        results_detail.get("summary", {}).get("summary_stats", {}).get("overall", {})
    )
    if overall:
        total_pass = int(overall.get("PASS", total_pass))
        total_fail = int(overall.get("FAIL", total_fail))
        total_error = int(overall.get("ERROR", total_error))
        eval_status, eval_score = _score_from_counts(
            total_pass, total_fail, total_error
        )
        result.update(
            {
                "eval_status": eval_status,
                "eval_score": eval_score,
                "pass": total_pass,
                "fail": total_fail,
                "error": total_error,
            }
        )
        results_detail.update(result)

    # Write results to Postgres so agentpod /evals/results can serve them
    try:
        from eval_postgres import write_eval_result

        write_eval_result(
            passed=total_pass,
            failed=total_fail,
            errors=total_error,
            eval_score=eval_score,
            results_detail=results_detail,
            ls_run_id=results_detail.get("ls_run_id"),
            config_hash=config_hash,
            org=org,
            name=name,
        )
    except Exception as exc:
        log.error("Postgres write failed (results still available locally): %s", exc)


# ── FastAPI app ────────────────────────────────────────────────────────────────
# eval_cases.yaml and system.yaml are pre-written to the PVC by agent-engine
# at deploy time — no startup auto-run or case management needed here.

app = FastAPI(title="eval-runner", version="2.0.0")


class EvalRunBody(BaseModel):
    """Request body for POST /evals/run — carries agent identity from the trigger response."""

    config_hash: str | None = None
    org: str | None = None
    name: str | None = None


def _extract_token(request: Request) -> str:
    """Extract user auth token from Authorization header (same pattern as agent).

    Falls back to the static AGENT_AUTH_TOKEN env var for local dev without auth.
    Raises 401 if ENABLE_AUTH is true and no token is found.
    """
    auth_header = request.headers.get("authorization", "")
    token = (
        auth_header.removeprefix("Bearer ").strip()
        if auth_header.startswith("Bearer ")
        else ""
    )
    token = token or AGENT_AUTH_TOKEN
    if ENABLE_AUTH and not token:
        raise HTTPException(status_code=401, detail="Authentication required")
    return token


async def _trigger(
    pattern: str | None,
    background: BackgroundTasks,
    body: EvalRunBody | None = None,
    auth_token: str = "",
) -> dict[str, Any]:
    if _status["state"] == "running":
        raise HTTPException(
            status_code=409, detail="An eval run is already in progress"
        )
    run_id = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    config_hash = body.config_hash if body else None
    org = body.org if body else None
    name = body.name if body else None
    background.add_task(_run_eval, pattern, config_hash, org, name, auth_token)
    return {
        "run_id": run_id,
        "status": "started",
        "pattern": pattern or "all",
    }


@app.post("/evals/run", status_code=202)
async def run_all(
    request: Request, background: BackgroundTasks, body: EvalRunBody = EvalRunBody()
) -> dict[str, Any]:
    """Run all eval patterns against the agent."""
    return await _trigger(None, background, body, _extract_token(request))


@app.post("/evals/run/{pattern}", status_code=202)
async def run_pattern(pattern: str, background: BackgroundTasks) -> dict[str, Any]:
    """Run one eval pattern (tool_use / hitl / structured_output / multi_agent)."""
    if pattern not in ALL_PATTERNS:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown pattern '{pattern}'. Valid: {ALL_PATTERNS}",
        )
    return await _trigger(pattern, background)


@app.get("/evals/status")
async def get_status() -> dict[str, Any]:
    """Return current run state: idle | running | completed | error."""
    return _status


@app.get("/evals/results")
async def get_latest_results() -> JSONResponse:
    """Return the latest run summary (in-memory)."""
    if _latest_result is None:
        raise HTTPException(status_code=404, detail="No eval results available yet")
    return JSONResponse(_latest_result)


@app.get("/evals/results/{run_id}")
async def get_run_results(run_id: str) -> JSONResponse:
    """Return results for a specific run ID from the evaluation_results Postgres table."""
    try:
        import psycopg2

        conn = psycopg2.connect(
            host=os.environ.get("POSTGRES_HOST", "localhost"),
            port=int(os.environ.get("POSTGRES_PORT", "5432")),
            dbname=os.environ.get("POSTGRES_DB", "template_agent"),
            user=os.environ.get("POSTGRES_USER", "postgres"),
            password=os.environ.get("POSTGRES_PASSWORD", ""),
            connect_timeout=5,
        )
        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT conversation_group_id, turn_id, metric_identifier, result, score, reason "
                    "FROM evaluation_results WHERE run_id = %s ORDER BY id",
                    (run_id,),
                )
                cols = [d[0] for d in cur.description]
                rows = [dict(zip(cols, r)) for r in cur.fetchall()]
        conn.close()
        if not rows:
            raise HTTPException(
                status_code=404, detail=f"No results found for run '{run_id}'"
            )
        return JSONResponse({"run_id": run_id, "results": rows})
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/health")
async def health() -> dict[str, str]:
    """Liveness probe — always returns ok."""
    return {"status": "ok"}


@app.post("/mcp")
async def mcp_stub() -> dict[str, str]:
    """Stub to suppress 404 noise from lightspeed-eval MCP probe on startup."""
    return {"error": "MCP not supported on eval runner"}
