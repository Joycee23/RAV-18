import json
import sys
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))
import evaluate_demo


@pytest.fixture
def evaluation_db():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    with factory() as session:
        yield session
    Base.metadata.drop_all(engine)
    engine.dispose()


def test_calculate_metrics_computes_classification_evidence_timestamp_and_latency():
    results = [
        {
            "expected_finding": True, "predicted_finding": True,
            "expected_evidence_indexes": [0, 1], "predicted_evidence_indexes": [0],
            "unmapped_evidence_id_count": 1,
            "expected_timestamp": "2026-01-01T00:00:00+00:00",
            "predicted_timestamp": "2026-01-01T00:00:01+00:00",
            "expected_workflow_steps": ["a", "b"], "completed_steps": ["a", "a"],
        },
        {
            "expected_finding": False, "predicted_finding": True,
            "expected_evidence_indexes": [], "predicted_evidence_indexes": [2],
            "unmapped_evidence_id_count": 0,
            "expected_timestamp": None, "predicted_timestamp": None,
            "expected_workflow_steps": ["a"], "completed_steps": ["a"],
        },
        {
            "expected_finding": False, "predicted_finding": False,
            "expected_evidence_indexes": [], "predicted_evidence_indexes": [],
            "unmapped_evidence_id_count": 0,
            "expected_timestamp": None, "predicted_timestamp": None,
            "expected_workflow_steps": [], "completed_steps": [],
        },
    ]

    metrics = evaluate_demo.calculate_metrics(results, [10.0, 20.0, 30.0])

    assert metrics["classification"] == {
        "tp": 1, "fp": 1, "tn": 1, "fn": 0,
        "accuracy": pytest.approx(2 / 3), "precision": pytest.approx(0.5),
        "recall": 1.0, "f1": pytest.approx(2 / 3),
    }
    assert metrics["evidence_grounding"] == {
        "true_positive": 1, "false_positive": 2, "false_negative": 1,
        "micro_precision": pytest.approx(1 / 3), "micro_recall": 0.5,
        "micro_f1": pytest.approx(0.4),
    }
    assert metrics["timestamp"] == {
        "compared_cases": 1, "mae_seconds": 1.0,
        "timestamp_within_tolerance_rate": 1.0,
    }
    assert metrics["completeness"] == {
        "completed_expected_steps": 2, "expected_steps": 3,
        "rate": pytest.approx(2 / 3),
    }
    assert metrics["latency_ms"] == {
        "samples": 3, "median": 20.0, "p95_nearest_rank": 30.0,
    }


def test_calculate_metrics_returns_null_for_undefined_denominators_and_missing_timestamps():
    metrics = evaluate_demo.calculate_metrics([], [])
    assert metrics["classification"]["accuracy"] is None
    assert metrics["classification"]["precision"] is None
    assert metrics["classification"]["recall"] is None
    assert metrics["classification"]["f1"] is None
    assert metrics["evidence_grounding"]["micro_precision"] is None
    assert metrics["evidence_grounding"]["micro_recall"] is None
    assert metrics["evidence_grounding"]["micro_f1"] is None
    assert metrics["timestamp"]["mae_seconds"] is None
    assert metrics["timestamp"]["timestamp_within_tolerance_rate"] is None
    assert metrics["completeness"]["rate"] is None
    assert metrics["latency_ms"]["median"] is None
    assert metrics["latency_ms"]["p95_nearest_rank"] is None

    timestamp_missing = [{
        "expected_finding": True, "predicted_finding": True,
        "expected_evidence_indexes": [], "predicted_evidence_indexes": [],
        "unmapped_evidence_id_count": 0, "expected_timestamp": None,
        "predicted_timestamp": "2026-01-01T00:00:00+00:00",
        "expected_workflow_steps": [], "completed_steps": [],
    }]
    assert evaluate_demo.calculate_metrics(timestamp_missing, [])[
        "timestamp"]["compared_cases"] == 0


def test_calculate_metrics_deduplicates_workflow_steps_and_applies_one_second_tolerance():
    result = {
        "expected_finding": True, "predicted_finding": True,
        "expected_evidence_indexes": [], "predicted_evidence_indexes": [],
        "unmapped_evidence_id_count": 0,
        "expected_timestamp": "2026-01-01T00:00:00+00:00",
        "predicted_timestamp": "2026-01-01T00:00:01.1+00:00",
        "expected_workflow_steps": ["step", "step"], "completed_steps": ["step", "step"],
    }
    metrics = evaluate_demo.calculate_metrics([result], [])
    assert metrics["completeness"]["expected_steps"] == 1
    assert metrics["completeness"]["completed_expected_steps"] == 1
    assert metrics["timestamp"]["mae_seconds"] == pytest.approx(1.1)
    assert metrics["timestamp"]["timestamp_within_tolerance_rate"] == 0.0


def test_calculate_metrics_returns_zero_f1_when_only_false_negatives_exist():
    result = {
        "expected_finding": True, "predicted_finding": False,
        "expected_evidence_indexes": [], "predicted_evidence_indexes": [],
        "unmapped_evidence_id_count": 0,
        "expected_timestamp": None, "predicted_timestamp": None,
        "expected_workflow_steps": [], "completed_steps": [],
    }

    classification = evaluate_demo.calculate_metrics([result], [])["classification"]

    assert classification["tp"] == 0
    assert classification["fp"] == 0
    assert classification["fn"] == 1
    assert classification["precision"] is None
    assert classification["recall"] == 0.0
    assert classification["f1"] == 0.0


def test_load_cases_rejects_empty_invalid_shape_timestamp_and_out_of_range_evidence(tmp_path):
    invalid_payloads = [
        ([], "non-empty"),
        ([{"id": "missing-fields"}], "missing required fields"),
    ]
    for payload, message in invalid_payloads:
        path = tmp_path / "cases.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        with pytest.raises(ValueError, match=message):
            evaluate_demo.load_cases(path)

    valid = json.loads((Path(__file__).parents[1] / "evaluation" / "cases.json").read_text())
    bad_timestamp = json.loads(json.dumps(valid[0]))
    bad_timestamp["events"][0]["timestamp"] = "2026-10-01T10:00:00"
    outside_index = json.loads(json.dumps(valid[0]))
    outside_index["expected_evidence_indexes"] = [1]
    for case, message in ((bad_timestamp, "UTC offset"), (outside_index, "outside evidence list")):
        path = tmp_path / "bad-case.json"
        path.write_text(json.dumps([case]), encoding="utf-8")
        with pytest.raises(ValueError, match=message):
            evaluate_demo.load_cases(path)


@pytest.mark.parametrize(("args", "message"), [
    (["--warmup", "-1"], "--warmup must be >= 0"),
    (["--repetitions", "0"], "--repetitions must be >= 1"),
])
def test_cli_rejects_invalid_run_counts(args, message, monkeypatch, capsys):
    monkeypatch.setattr("sys.argv", ["evaluate_demo", *args])
    assert evaluate_demo.main() == 2
    assert message in capsys.readouterr().err


def test_cli_rejects_bad_dataset_without_success_report(tmp_path, monkeypatch, capsys):
    bad_cases = tmp_path / "empty.json"
    bad_cases.write_text("[]", encoding="utf-8")
    monkeypatch.setattr("sys.argv", ["evaluate_demo", "--cases", str(bad_cases)])
    assert evaluate_demo.main() == 2
    captured = capsys.readouterr()
    assert "non-empty" in captured.err
    assert captured.out == ""


def test_evaluate_case_maps_unknown_evidence_id_as_unmapped_false_positive(evaluation_db, monkeypatch):
    event_time = "2026-10-01T10:00:00+00:00"
    case = {
        "id": "unknown-id", "events": [{
            "timestamp": event_time, "source": "test", "event_type": "alert", "message": "sample",
        }],
        "evidence": [{
            "timestamp": event_time, "evidence_type": "log", "label": "log", "description": "sample",
        }],
        "expected_finding": True, "expected_evidence_indexes": [0],
        "expected_timestamp": event_time, "expected_workflow_steps": [],
    }
    monkeypatch.setattr(evaluate_demo, "run_analysis", lambda *_: SimpleNamespace(
        findings=[SimpleNamespace(evidence_ids=["unknown-evidence-id"], timestamp=datetime.fromisoformat(event_time))],
        steps=[],
    ))

    result = evaluate_demo.evaluate_case(evaluation_db, case)

    assert result["predicted_evidence_indexes"] == []
    assert result["unmapped_evidence_ids"] == ["unknown-evidence-id"]
    assert result["unmapped_evidence_id_count"] == 1
    metrics = evaluate_demo.calculate_metrics([result], [])
    assert metrics["evidence_grounding"]["false_positive"] == 1
    assert metrics["evidence_grounding"]["false_negative"] == 1


def test_dataset_pipeline_predictions_match_synthetic_labels():
    cases_path = Path(__file__).parents[1] / "evaluation" / "cases.json"
    cases = evaluate_demo.load_cases(cases_path)
    results = [evaluate_demo._run_one(case) for case in cases]
    for result in results:
        assert result["predicted_finding"] is result["expected_finding"], result["case_id"]
        assert result["predicted_evidence_indexes"] == result["expected_evidence_indexes"], result["case_id"]
        assert result["predicted_timestamp"] == result["expected_timestamp"]
        assert set(result["expected_workflow_steps"]) <= set(result["completed_steps"])


def test_cli_default_dataset_and_json_output_are_valid(tmp_path, monkeypatch, capsys):
    output_path = tmp_path / "report.json"
    monkeypatch.setattr("sys.argv", ["evaluate_demo", "--warmup", "0", "--repetitions", "1", "--json", str(output_path)])

    assert evaluate_demo.main() == 0
    stdout_report = json.loads(capsys.readouterr().out)
    file_report = json.loads(output_path.read_text(encoding="utf-8"))
    assert stdout_report["mode"] == "deterministic_synthetic"
    assert stdout_report["model_used"] is False
    assert stdout_report["case_count"] == 5
    assert stdout_report["configuration"]["warmup_per_case"] == 0
    assert stdout_report["configuration"]["repetitions_per_case"] == 1
    assert file_report == stdout_report
