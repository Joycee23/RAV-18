"""Offline benchmark for IncidentLens' deterministic synthetic analysis."""

from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

# The app's shared settings normally load `.env` at import time. Disable dotenv
# for this isolated CLI so the benchmark cannot inherit a user's Supabase URL.
from app import config as app_config

app_config.Settings.model_config = {**app_config.Settings.model_config, "env_file": None}

from app.db import Base
from app.models import Evidence, Incident, LogEvent
from app.services.analysis import run_analysis

WORKFLOW_STEPS = {
    "load_incident", "read_drive_logs", "sample_video_metadata",
    "align_timeline", "draft_report",
}
NAMESPACE = uuid.UUID("486b2c61-512e-4d44-9052-fca332594f19")
REQUIRED_CASE_FIELDS = {
    "id", "events", "evidence", "expected_finding",
    "expected_evidence_indexes", "expected_timestamp", "expected_workflow_steps",
}


def _parse_timestamp(value: Any, field: str, *, nullable: bool = False) -> datetime | None:
    if value is None and nullable:
        return None
    if not isinstance(value, str):
        raise ValueError(f"{field} must be an ISO-8601 timestamp" + (" or null" if nullable else ""))
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{field} is not a valid ISO-8601 timestamp: {value!r}") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"{field} must include a UTC offset")
    return parsed.astimezone(UTC)


def _validate_case(case: Any, index: int) -> None:
    prefix = f"case[{index}]"
    if not isinstance(case, dict):
        raise ValueError(f"{prefix} must be an object")
    missing = REQUIRED_CASE_FIELDS - case.keys()
    if missing:
        raise ValueError(f"{prefix} missing required fields: {', '.join(sorted(missing))}")
    if not isinstance(case["id"], str) or not case["id"].strip():
        raise ValueError(f"{prefix}.id must be a non-empty string")
    if not isinstance(case["events"], list) or not isinstance(case["evidence"], list):
        raise ValueError(f"{prefix}.events and {prefix}.evidence must be lists")
    for group in ("events", "evidence"):
        fields = ("timestamp", "source", "event_type", "message") if group == "events" else ("timestamp", "evidence_type", "label", "description")
        for row_index, row in enumerate(case[group]):
            if not isinstance(row, dict):
                raise ValueError(f"{prefix}.{group}[{row_index}] must be an object")
            absent = set(fields) - row.keys()
            if absent:
                raise ValueError(f"{prefix}.{group}[{row_index}] missing fields: {', '.join(sorted(absent))}")
            _parse_timestamp(row["timestamp"], f"{prefix}.{group}[{row_index}].timestamp")
            for field in fields[1:]:
                if not isinstance(row[field], str):
                    raise ValueError(f"{prefix}.{group}[{row_index}].{field} must be a string")
    if not isinstance(case["expected_finding"], bool):
        raise ValueError(f"{prefix}.expected_finding must be boolean")
    evidence_indexes = case["expected_evidence_indexes"]
    if not isinstance(evidence_indexes, list) or any(type(value) is not int for value in evidence_indexes):
        raise ValueError(f"{prefix}.expected_evidence_indexes must be a list of integer indexes")
    if any(value < 0 or value >= len(case["evidence"]) for value in evidence_indexes):
        raise ValueError(f"{prefix}.expected_evidence_indexes contains an index outside evidence list")
    _parse_timestamp(case["expected_timestamp"], f"{prefix}.expected_timestamp", nullable=True)
    if not isinstance(case["expected_workflow_steps"], list) or any(not isinstance(step, str) for step in case["expected_workflow_steps"]):
        raise ValueError(f"{prefix}.expected_workflow_steps must be a list of strings")
    unknown_steps = set(case["expected_workflow_steps"]) - WORKFLOW_STEPS
    if unknown_steps:
        raise ValueError(f"{prefix}.expected_workflow_steps has unknown steps: {', '.join(sorted(unknown_steps))}")


def load_cases(path: Path) -> list[dict]:
    """Read and validate all cases, failing before any benchmark report is produced."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ValueError(f"cannot read cases file {path}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid JSON in cases file {path}: {exc}") from exc
    if not isinstance(data, list) or not data:
        raise ValueError("cases file must contain a non-empty JSON list")
    seen: set[str] = set()
    for index, case in enumerate(data):
        _validate_case(case, index)
        if case["id"] in seen:
            raise ValueError(f"duplicate case id: {case['id']}")
        seen.add(case["id"])
    return data


def _stable_id(case_id: str, kind: str, index: int = 0) -> uuid.UUID:
    return uuid.uuid5(NAMESPACE, f"{case_id}:{kind}:{index}")


def evaluate_case(db: Session, case: dict) -> dict:
    """Load one synthetic case into the provided in-memory DB and call the real pipeline."""
    case_id = case["id"]
    incident_id = _stable_id(case_id, "incident")
    incident_time = _parse_timestamp(case["events"][0]["timestamp"], "event timestamp") if case["events"] else datetime(2000, 1, 1, tzinfo=UTC)
    db.add(Incident(
        id=incident_id, title=f"Synthetic benchmark: {case_id}", severity="low", status="open",
        occurred_at=incident_time, vehicle_id=f"SIM-{case_id}", summary="Synthetic benchmark fixture.",
        metadata_json={"dataset": "synthetic", "label": "SIMULATED"},
    ))
    for event_index, event in enumerate(case["events"]):
        db.add(LogEvent(
            id=_stable_id(case_id, "event", event_index), incident_id=incident_id,
            timestamp=_parse_timestamp(event["timestamp"], f"event[{event_index}].timestamp"),
            source=event["source"], event_type=event["event_type"], message=event["message"],
            details={"label": "SIMULATED"},
        ))
    evidence_by_id: dict[str, int] = {}
    for evidence_index, evidence in enumerate(case["evidence"]):
        evidence_id = _stable_id(case_id, "evidence", evidence_index)
        evidence_by_id[str(evidence_id)] = evidence_index
        db.add(Evidence(
            id=evidence_id, incident_id=incident_id,
            timestamp=_parse_timestamp(evidence["timestamp"], f"evidence[{evidence_index}].timestamp"),
            evidence_type=evidence["evidence_type"], label=evidence["label"], description=evidence["description"],
            metadata_json={"label": evidence.get("label", "SIMULATED"), "media_interpretation": "metadata_only"},
        ))
    db.commit()

    started = time.perf_counter()
    run = run_analysis(db, incident_id)
    duration_ms = (time.perf_counter() - started) * 1000
    finding = run.findings[0] if run.findings else None
    predicted_indexes: set[int] = set()
    unmapped_ids: list[str] = []
    if finding:
        for evidence_id in finding.evidence_ids:
            index = evidence_by_id.get(str(evidence_id))
            if index is None:
                unmapped_ids.append(str(evidence_id))
            else:
                predicted_indexes.add(index)
    completed_steps = [step.name for step in run.steps if step.status == "completed"]
    expected_timestamp = _parse_timestamp(case["expected_timestamp"], "expected_timestamp", nullable=True)
    predicted_timestamp = run.findings[0].timestamp if finding else None
    if predicted_timestamp is not None:
        predicted_timestamp = predicted_timestamp.replace(tzinfo=UTC) if predicted_timestamp.tzinfo is None else predicted_timestamp.astimezone(UTC)
    compare_timestamp = bool(case["expected_finding"] and finding and expected_timestamp and predicted_timestamp)
    return {
        "case_id": case_id,
        "expected_finding": case["expected_finding"],
        "predicted_finding": bool(finding),
        "expected_evidence_indexes": sorted(set(case["expected_evidence_indexes"])),
        "predicted_evidence_indexes": sorted(predicted_indexes),
        "unmapped_evidence_ids": unmapped_ids,
        "unmapped_evidence_id_count": len(unmapped_ids),
        "expected_timestamp": expected_timestamp.isoformat() if expected_timestamp else None,
        "predicted_timestamp": predicted_timestamp.isoformat() if predicted_timestamp else None,
        "timestamp_exclusion_reason": None if compare_timestamp else (
            "expected case has no finding" if not case["expected_finding"] else
            "pipeline predicted no finding" if not finding else
            "expected or predicted timestamp is missing"
        ),
        "completed_steps": completed_steps,
        "expected_workflow_steps": case["expected_workflow_steps"],
        "duration_ms": duration_ms,
    }


def _ratio(numerator: float, denominator: float) -> float | None:
    return numerator / denominator if denominator else None


def calculate_metrics(case_results: list[dict], latencies_ms: list[float]) -> dict:
    tp = sum(r["expected_finding"] and r["predicted_finding"] for r in case_results)
    fp = sum(not r["expected_finding"] and r["predicted_finding"] for r in case_results)
    tn = sum(not r["expected_finding"] and not r["predicted_finding"] for r in case_results)
    fn = sum(r["expected_finding"] and not r["predicted_finding"] for r in case_results)
    precision, recall = _ratio(tp, tp + fp), _ratio(tp, tp + fn)

    ev_tp = ev_fp = ev_fn = 0
    timestamp_errors: list[float] = []
    expected_step_count = completed_step_count = 0
    for result in case_results:
        expected = set(result["expected_evidence_indexes"])
        predicted = set(result["predicted_evidence_indexes"])
        ev_tp += len(expected & predicted)
        ev_fp += len(predicted - expected) + result.get("unmapped_evidence_id_count", 0)
        ev_fn += len(expected - predicted)
        if result["expected_finding"] and result["predicted_finding"]:
            expected_ts, predicted_ts = result.get("expected_timestamp"), result.get("predicted_timestamp")
            if expected_ts and predicted_ts:
                expected_dt = _parse_timestamp(expected_ts, "expected_timestamp")
                predicted_dt = _parse_timestamp(predicted_ts, "predicted_timestamp")
                timestamp_errors.append(abs((predicted_dt - expected_dt).total_seconds()))
        expected_steps = set(result["expected_workflow_steps"])
        completed_steps = set(result["completed_steps"])
        expected_step_count += len(expected_steps)
        completed_step_count += len(expected_steps & completed_steps)

    ev_precision, ev_recall = _ratio(ev_tp, ev_tp + ev_fp), _ratio(ev_tp, ev_tp + ev_fn)
    ev_f1 = _ratio(2 * ev_tp, 2 * ev_tp + ev_fp + ev_fn)
    latency_values = sorted(latencies_ms)
    p95 = latency_values[math.ceil(0.95 * len(latency_values)) - 1] if latency_values else None
    return {
        "classification": {
            "tp": tp, "fp": fp, "tn": tn, "fn": fn,
            "accuracy": _ratio(tp + tn, len(case_results)),
            "precision": precision, "recall": recall,
            "f1": _ratio(2 * tp, 2 * tp + fp + fn),
        },
        "evidence_grounding": {
            "true_positive": ev_tp, "false_positive": ev_fp, "false_negative": ev_fn,
            "micro_precision": ev_precision, "micro_recall": ev_recall, "micro_f1": ev_f1,
        },
        "timestamp": {
            "compared_cases": len(timestamp_errors),
            "mae_seconds": statistics.mean(timestamp_errors) if timestamp_errors else None,
            "timestamp_within_tolerance_rate": sum(error <= 1.0 for error in timestamp_errors) / len(timestamp_errors) if timestamp_errors else None,
        },
        "completeness": {
            "completed_expected_steps": completed_step_count,
            "expected_steps": expected_step_count,
            "rate": _ratio(completed_step_count, expected_step_count),
        },
        "latency_ms": {
            "samples": len(latency_values),
            "median": statistics.median(latency_values) if latency_values else None,
            "p95_nearest_rank": p95,
        },
    }


def _run_one(case: dict) -> dict:
    engine = create_engine("sqlite://")
    try:
        Base.metadata.create_all(engine)
        factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
        with factory() as session:
            return evaluate_case(session, case)
    finally:
        engine.dispose()


def main() -> int:
    parser = argparse.ArgumentParser(description="Benchmark the deterministic synthetic IncidentLens pipeline offline.")
    default_cases = Path(__file__).resolve().parents[1] / "evaluation" / "cases.json"
    parser.add_argument("--cases", type=Path, default=default_cases, help="path to benchmark cases JSON")
    parser.add_argument("--warmup", type=int, default=1, help="unmeasured warmup runs per case (must be >= 0)")
    parser.add_argument("--repetitions", type=int, default=5, help="measured runs per case (must be >= 1)")
    parser.add_argument("--json", type=Path, help="also write report JSON to this path")
    args = parser.parse_args()
    if args.warmup < 0:
        print("error: --warmup must be >= 0", file=sys.stderr)
        return 2
    if args.repetitions < 1:
        print("error: --repetitions must be >= 1", file=sys.stderr)
        return 2
    try:
        cases = load_cases(args.cases)
        quality_results: list[dict] = []
        latencies: list[float] = []
        for case in cases:
            for _ in range(args.warmup):
                _run_one(case)
            case_runs = [_run_one(case) for _ in range(args.repetitions)]
            result = {key: value for key, value in case_runs[0].items() if key != "duration_ms"}
            result["duration_ms"] = statistics.median(run["duration_ms"] for run in case_runs)
            quality_results.append(result)
            latencies.extend(run["duration_ms"] for run in case_runs)
        report = {
            "mode": "deterministic_synthetic", "model_used": False, "case_count": len(cases),
            "configuration": {"warmup_per_case": args.warmup, "repetitions_per_case": args.repetitions, "python_version": sys.version.split()[0]},
            "metrics": calculate_metrics(quality_results, latencies), "results": quality_results,
        }
        output = json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False)
        if args.json:
            args.json.write_text(output + "\n", encoding="utf-8")
        print(output)
        return 0
    except Exception as exc:
        print(f"error: benchmark failed: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
