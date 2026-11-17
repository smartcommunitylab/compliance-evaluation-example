"""Independent DH project function: model measurements -> compliance reports."""

import hashlib
import json
import logging
import tempfile
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from loan_evaluation import (
    CONTRACT,
    DECISION_THRESHOLD,
    IMPLEMENTATION_SHA256,
    _envelope,
    evaluate_calibration,
    evaluate_explanations,
    evaluate_membership,
    evaluate_robustness,
    evaluate_saved_metric,
)


LOGGER = logging.getLogger(__name__)
REPORT_NAMES = {"EVALUATION": "loan-model-evaluation", "TEST": "loan-model-test"}


def _scalar_metrics(metrics):
    values = {}
    for name, value in metrics.items():
        if isinstance(value, list):
            if len(value) != 1:
                raise ValueError(f"Metric {name} has multiple values; an explicit step selector is required")
            value = value[0]
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not np.isfinite(value):
            raise ValueError(f"Metric {name} must be a finite numeric value")
        values[name] = value
    return values


def _training_evidence(entity):
    evidence = (entity.spec.parameters or {}).get("training_evidence")
    if evidence is None:
        return None, {}
    if evidence["protocol"] != "historical-approval-v1" or evidence["target"] != "Loan_Approval_Status":
        raise ValueError("The model's target/protocol is not approved for this evaluation")
    if evidence["positive_label"] != 1 or evidence["decision_threshold"] != DECISION_THRESHOLD:
        raise ValueError("Model label/threshold differs from the approved evaluation contract")
    if evidence["dataset_key"] != CONTRACT["dataset_key"]:
        raise ValueError("Model was trained on a different dataset version")
    metrics = _scalar_metrics(entity.metrics)
    if metrics != evidence["metrics_snapshot"]:
        raise ValueError("Model metrics differ from the provenance-bound training snapshot")
    return evidence, metrics


def _dataset_context(loan_data, evidence, context):
    if loan_data.key != evidence["dataset_key"]:
        raise ValueError("Optional dataset does not match the model's training dataset version")
    frame = loan_data.as_df()
    if not isinstance(frame, pd.DataFrame) or not frame.columns.is_unique:
        raise TypeError("The training dataset must expose a DataFrame with unique columns")
    frame = frame.reset_index(drop=True)
    digest = hashlib.sha256()
    digest.update(json.dumps([(str(column), str(dtype)) for column, dtype in frame.dtypes.items()]).encode())
    digest.update(pd.util.hash_pandas_object(frame, index=False).to_numpy().tobytes())
    if digest.hexdigest() != evidence["dataset_fingerprint"]:
        raise ValueError("Dataset rows, order or schema differ from the training fingerprint")
    train_ids, test_ids = evidence["train_row_ids"], evidence["test_row_ids"]
    eligible = set(frame.index[frame["Loan_Approval_Status"].notna()])
    if len(set(train_ids)) != len(train_ids) or len(set(test_ids)) != len(test_ids):
        raise ValueError("Persisted split contains duplicate row IDs")
    if set(train_ids).intersection(test_ids) or set(train_ids).union(test_ids) != eligible:
        raise ValueError("Persisted split is overlapping or incomplete")
    return {
        **context, "train": frame.loc[train_ids], "test": frame.loc[test_ids],
        "feature_columns": evidence["feature_columns"],
        "measurement_source": "model-and-dataset computation",
        "measured_at": None,
    }


def _measurements(entity, loan_data=None):
    if entity.project != CONTRACT["project"] or entity.name != CONTRACT["entity"]:
        raise ValueError("The model does not match loan-app3/loan-approval-classifier")
    evidence, metrics = _training_evidence(entity)
    target = {
        "project": entity.project, "entity": entity.name,
        "key": entity.key, "version": entity.metadata.version,
    }
    context = {
        "model_key": entity.key, "dataset_key": CONTRACT["dataset_key"],
        "run_key": evidence["run_key"] if evidence else None,
        "decision_threshold": DECISION_THRESHOLD,
        "implementation_sha256": IMPLEMENTATION_SHA256,
        "training_evidence": evidence, "model_metrics": metrics,
        "measurement_source": "saved training metrics",
        "measured_at": evidence["measured_at"] if evidence else None,
    }
    results = [
        evaluate_saved_metric(target, context, metric_id, name) for metric_id, name in (
            ("metric-equalized-odds-difference", "equalized_odds_difference"),
            ("metric-auc-roc", "roc_auc"),
            ("metric-expected-calibration-error", "expected_calibration_error"),
        )
    ]
    results.append(evaluate_robustness(target, context))
    if loan_data is None or evidence is None:
        reason = (
            "Optional training dataset was not supplied"
            if evidence else "Model lacks saved split membership/provenance; retraining is required"
        )
        for metric_id in ("metric-decision-coverage", "metric-membership-inference-auc"):
            results.append(_envelope(target, context, metric_id, None, {}, reason))
        return results
    context = _dataset_context(loan_data, evidence, context)
    with tempfile.TemporaryDirectory() as directory:
        path = Path(entity.download(destination=str(Path(directory) / "model.joblib")))
        if not path.is_file():
            raise ValueError("Expected the selected sklearn model to download as one file")
        if hashlib.sha256(path.read_bytes()).hexdigest() != evidence["model_sha256"]:
            raise ValueError("Downloaded model does not match its training artifact hash")
        target["estimator"] = joblib.load(path)
        if target["estimator"].feature_names_in_.tolist() != evidence["feature_columns"]:
            raise ValueError("Model input features do not match persisted training evidence")
        results.extend([evaluate_explanations(target, context), evaluate_membership(target, context)])
        calibration = evaluate_calibration(target, context)
        if not np.isclose(calibration["metric_result"]["value"], metrics["expected_calibration_error"], atol=1e-12):
            raise ValueError("Recomputed calibration does not match the stored model metric")
        results[2] = calibration
    return results


def build_reports(measurements, operation_key=None):
    metrics, checks, verdicts, issues = [], [], [], []
    for measurement in measurements:
        reference = measurement["objective_ref"]
        result = measurement["metric_result"]
        assessment = measurement["evidence"]["assessment"]
        if result is not None:
            metrics.append(result)
        if assessment["determinate"]:
            passed = assessment["status"] == "pass"
            checks.append({
                "measured": json.dumps(result["value"], allow_nan=False),
                "expected": measurement["objective"]["condition"], "passed": passed,
                "details": reference,
            })
            verdicts.append("PASS" if passed else "FAIL")
        else:
            verdicts.append("INCONCLUSIVE")
            issues.append(f"{reference}: {assessment['reason']}")
    if not verdicts:
        raise ValueError("Cannot build a report without objective results")
    verdict = next(status for status in ("ERROR", "FAIL", "INCONCLUSIVE", "PASS") if status in verdicts)
    references = [measurement["objective_ref"] for measurement in measurements]
    evidence_summary = json.dumps([
        {
            "error": measurement["error"],
            "provenance": measurement["provenance"],
        }
        for measurement in measurements
    ], allow_nan=False)
    sources = [{"key": key} for key in sorted({
        source for measurement in measurements
        for source in (
            measurement["provenance"]["model_key"],
            measurement["provenance"]["dataset_key"],
            measurement["provenance"]["run_key"],
        ) if source
    })]
    lineage = {"sources": sources}
    if operation_key:
        lineage["operation"] = {"key": operation_key}
    return {
        "EVALUATION": {
            "kind": "EVALUATION",
            "objectives": references,
            "content": {"evaluation": {"metrics": metrics, "summary": evidence_summary}},
            "lineage": lineage,
        },
        "TEST": {
            "kind": "TEST", "objectives": references,
            "content": {"test": {
                "results": checks, "verdict": verdict,
                "summary": "; ".join(issues) or "All objective checks are determinate.",
            }},
            "lineage": lineage,
        },
    }


def run(project, entity, loan_data=None, run=None):
    """Read model metrics; optionally test with training data; always attach the reports."""
    if project.name != CONTRACT["project"] or project.name != entity.project:
        raise ValueError("Project and selected model must both belong to loan-app3")
    expected = CONTRACT["objectives"]
    specifications = [
        extension["spec"] for extension in entity.extensions or []
        if extension.get("kind") == "model-compliance"
    ]
    if len(specifications) > 1 or (specifications and specifications[0].get("objectives") != expected):
        raise ValueError("Model compliance specification changed; review before evaluating or attaching reports")
    measurements = _measurements(entity, loan_data)
    for measurement in measurements:
        if not measurement["evidence"]["assessment"]["determinate"]:
            LOGGER.warning("%s: %s", measurement["objective_ref"], measurement["error"])
    reports = build_reports(measurements, getattr(run, "key", None))
    existing = [
        extension for extension in entity.extensions or []
        if not (extension.get("kind") == "compliance-report"
                and extension.get("name") in REPORT_NAMES.values())
    ]
    if not specifications:
        existing.append({
            "kind": "model-compliance", "name": "model-compliance",
            "spec": {"objectives": expected},
        })
    entity.extensions = existing + [
        {"kind": "compliance-report", "name": REPORT_NAMES[kind],
         "spec": {"name": REPORT_NAMES[kind], **report}}
        for kind, report in reports.items()
    ]
    entity.save(update=True)
    return {
        "model_key": entity.key, "model_version": entity.metadata.version,
        "published": True, "reports": reports, "measurements": measurements,
        "publication_policy": (
            "Always attaches the approved specification if missing and overwrites same-named "
            "reports; conflicting specifications rejected; no atomicity guarantee"
        ),
    }
