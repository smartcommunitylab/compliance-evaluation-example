"""Read-only, offline evaluators for the approved historical-approval contract."""

import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, roc_auc_score
from sklearn.model_selection import train_test_split
from sklearn.tree import DecisionTreeClassifier


CONTRACT = json.loads("{\"project\": \"loan-app3\", \"entity\": \"loan-approval-classifier\", \"specification_model_key\": \"store://loan-app3/model/sklearn/loan-approval-classifier:81f1811cff17415c9c203d8953e47b5c\", \"specification_model_version\": \"brisk-crane\", \"extension_key\": \"store://loan-app3/extension/model-compliance/model-compliance:cae1f90f9ba24e73843519a0cec3356d\", \"objectives\": [{\"name\": \"Group error-rate parity\", \"description\": \"On held-out applicants, measure maximum TPR/FPR difference across gender, age and socioeconomic-proxy groups; investigate intersectional gaps and proxy discrimination.\", \"metric\": {\"id\": \"metric-equalized-odds-difference\", \"name\": \"Equalized Odds Difference\", \"description\": \"Maximum absolute difference in true positive rate and false positive rate across\", \"kind\": \"COMPOSITE\", \"scale\": \"RATIO\", \"unit\": {\"symbol\": \"\\u0394\", \"name\": \"rate difference\"}, \"range\": {\"lower\": 0.0, \"upper\": 1.0, \"discrete\": false}}, \"condition\": {\"threshold\": {\"operator\": \"LEQ\", \"value\": 0.05}}, \"priority\": \"MANDATORY\", \"severity\": \"HIGH\", \"requirements\": [\"req-euai-art-10\", \"req-eucharter-art-21\", \"req-eba-demographic_bias\"], \"rationale\": \"Addresses protected-group disparity and proxy discrimination; use gender only for permitted fairness analysis, not as a model input.\"}, {\"name\": \"Discriminative performance\", \"description\": \"Evaluate ranking quality on a representative, held-out applicant set using the approved target and document subgroup results.\", \"metric\": {\"id\": \"metric-auc-roc\", \"name\": \"AUC-ROC (Area Under ROC Curve)\", \"description\": \"Area under the Receiver Operating Characteristic curve. Measures the model's abi\", \"kind\": \"PRIMITIVE\", \"scale\": \"RATIO\", \"unit\": {\"symbol\": \"AUC\", \"name\": \"area\"}, \"range\": {\"lower\": 0.0, \"upper\": 1.0, \"discrete\": false}}, \"condition\": {\"threshold\": {\"operator\": \"GEQ\", \"value\": 0.85}}, \"priority\": \"MANDATORY\", \"severity\": \"HIGH\", \"requirements\": [\"req-euai-art-15\"], \"rationale\": \"The OKF identifies AUC \\u2265 0.85 as a common minimum for high-risk credit scoring; confirm against the approved target and deployment population.\"}, {\"name\": \"Adversarial robustness\", \"description\": \"Measure accuracy on perturbed but valid applicant inputs under documented attack budgets, detecting crafted inputs that alter the risk classification.\", \"metric\": {\"id\": \"metric-adversarial-accuracy\", \"name\": \"Adversarial Accuracy\", \"description\": \"Model accuracy on adversarially perturbed inputs. Measures how much accuracy deg\", \"kind\": \"PRIMITIVE\", \"scale\": \"RATIO\", \"unit\": {\"symbol\": \"%\", \"name\": \"percent\"}, \"range\": {\"lower\": 0.0, \"upper\": 1.0, \"discrete\": false}}, \"condition\": {\"threshold\": {\"operator\": \"GEQ\", \"value\": 0.8}}, \"priority\": \"MANDATORY\", \"severity\": \"HIGH\", \"requirements\": [\"req-euai-art-15\"], \"rationale\": \"Addresses adversarial-input misuse and Art. 15 robustness; attack budget and feature-validity constraints must be fixed in the protocol.\"}, {\"name\": \"Traceable explanations for human review\", \"description\": \"Ensure at least 95% of applicant predictions have a traceable rationale available to loan officers; preserve their ability to reject, override or escalate the advisory signal.\", \"metric\": {\"id\": \"metric-decision-coverage\", \"name\": \"Decision Coverage (Traceable Predictions)\", \"description\": \"Fraction of model predictions for which a traceable decision path or rule-based \", \"kind\": \"PRIMITIVE\", \"scale\": \"RATIO\", \"unit\": {\"symbol\": \"%\", \"name\": \"percent\"}, \"range\": {\"lower\": 0.0, \"upper\": 1.0, \"discrete\": false}}, \"condition\": {\"threshold\": {\"operator\": \"GEQ\", \"value\": 0.95}}, \"priority\": \"MANDATORY\", \"severity\": \"HIGH\", \"requirements\": [\"req-euai-art-13\", \"req-euai-art-14\", \"req-gdpr-art-22\", \"req-eucharter-art-47\"], \"rationale\": \"Supports transparent interpretation and counters automation bias; explanation fidelity and reviewer authority/training require separate validation.\"}, {\"name\": \"Probability calibration\", \"description\": \"On held-out applicants, verify predicted repayment-risk probabilities are calibrated and report calibration by demographic groups.\", \"metric\": {\"id\": \"metric-expected-calibration-error\", \"name\": \"Expected Calibration Error (ECE)\", \"description\": \"Weighted average absolute difference between predicted confidence and empirical \", \"kind\": \"PRIMITIVE\", \"scale\": \"RATIO\", \"unit\": {\"symbol\": \"ECE\", \"name\": \"calibration error\"}, \"range\": {\"lower\": 0.0, \"upper\": 1.0, \"discrete\": false}}, \"condition\": {\"threshold\": {\"operator\": \"LEQ\", \"value\": 0.02}}, \"priority\": \"RECOMMENDED\", \"severity\": \"HIGH\", \"requirements\": [\"req-euai-art-15\"], \"rationale\": \"The OKF identifies ECE below 0.02 as generally acceptable for high-stakes uses; confirm binning and calibration data.\"}, {\"name\": \"Membership-inference resistance\", \"description\": \"Test whether an attacker can infer applicant-record membership in the training data from model outputs; keep attack AUC near chance.\", \"metric\": {\"id\": \"metric-membership-inference-auc\", \"name\": \"Membership Inference Attack AUC\", \"description\": \"AUC of a membership inference attack classifier distinguishing training members \", \"kind\": \"PRIMITIVE\", \"scale\": \"RATIO\", \"unit\": {\"symbol\": \"AUC\", \"name\": \"area\"}, \"range\": {\"lower\": 0.5, \"upper\": 1.0, \"discrete\": false}}, \"condition\": {\"threshold\": {\"operator\": \"LEQ\", \"value\": 0.6}}, \"priority\": \"MANDATORY\", \"severity\": \"HIGH\", \"requirements\": [\"req-gdpr-art-5\"], \"rationale\": \"The training data contains applicant identifiers and demographic/financial fields; the OKF says attack AUC above 0.6 warrants investigation.\"}], \"dataset_key\": \"store://loan-app3/dataitem/table/loan_dataset:2d76c2b381ec47b9b00e8b7ed78cd234\", \"bundle_version\": \"79da8bd1b27a\", \"grounding\": {\"metric-equalized-odds-difference\": [\"catalog/metrics/fairness/equalized-odds-difference.md\", \"a50874880eafc6712cea3f9966545a2000354259451bddc91c47e2897878c4fe\"], \"metric-auc-roc\": [\"catalog/metrics/performance/auc-roc.md\", \"0c9c20fd3dd2afa4668f83fdb6260e33a5e2530fff19992fb9b838784ccf81b6\"], \"metric-adversarial-accuracy\": [\"catalog/metrics/robustness/adversarial-accuracy.md\", \"805f83bbf6a3f5c6e42c73fe3db1cfb5adcbc6270c4e1b18bbb085a64df46877\"], \"metric-decision-coverage\": [\"catalog/metrics/explainability/decision-coverage.md\", \"bf17a29c0e837426f5d24b8b5f3eb3fffd30d37eb4f46a77f4167e64bb6f59ad\"], \"metric-expected-calibration-error\": [\"catalog/metrics/calibration/expected-calibration-error.md\", \"2e3fc491cc03657cf68e5e6a01bef60f4e52f8f21ff627a3614131651a1e6bc7\"], \"metric-membership-inference-auc\": [\"catalog/metrics/privacy/membership-inference-auc.md\", \"9795c06cc2f478c822c85412d8f01244cb306a679e9ef773134c1ffe29c933ab\"]}}")
IMPLEMENTATION_SHA256 = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
DECISION_THRESHOLD = 0.90
MIN_CLASS_SUPPORT = 30
MAIN_SLICES = ("Gender", "age_band", "income_band")
ALL_SLICES = (*MAIN_SLICES, "gender_age", "gender_income")


def _validate(entity: Mapping[str, Any], context: Mapping[str, Any]) -> None:
    if entity["project"] != CONTRACT["project"] or entity["entity"] != CONTRACT["entity"]:
        raise ValueError("Evaluation target does not match the approved project/model")
    if not entity["key"] or not entity["version"]:
        raise ValueError("An exact model key and version are required")
    if context["model_key"] != entity["key"]:
        raise ValueError("Evaluation evidence belongs to a different model")
    if context["dataset_key"] != CONTRACT["dataset_key"]:
        raise ValueError("Evaluation dataset differs from the approved version")
    if context["decision_threshold"] != DECISION_THRESHOLD:
        raise ValueError("The approved historical-approval threshold is 0.90")
    if "train" not in context:
        return
    train, test = context["train"], context["test"]
    if train.empty or test.empty or not train.index.is_unique or not test.index.is_unique:
        raise ValueError("Nonempty partitions with unique row identifiers are required")
    if not train.index.intersection(test.index).empty:
        raise ValueError("Training members and held-out non-members overlap")
    for frame in (train, test):
        labels = frame["Loan_Approval_Status"].to_numpy()
        if not np.isin(labels, [0, 1]).all():
            raise ValueError("Evaluation labels must be binary, non-null approval outcomes")
        if "Applicant_ID" in frame and (
            frame["Applicant_ID"].isna().any() or frame["Applicant_ID"].duplicated().any()
        ):
            raise ValueError("Applicant_ID must be non-null and unique within each partition")
    if "Applicant_ID" in train and "Applicant_ID" in test:
        if set(train["Applicant_ID"]).intersection(test["Applicant_ID"]):
            raise ValueError("Applicants overlap across training and evaluation partitions")


def _probabilities(entity: Mapping[str, Any], frame: pd.DataFrame, context: Mapping[str, Any]):
    estimator = entity["estimator"]
    position = list(estimator.classes_).index(1)
    probabilities = np.asarray(
        estimator.predict_proba(frame[context["feature_columns"]])[:, position], dtype=float
    )
    if probabilities.shape != (len(frame),):
        raise ValueError("Expected one positive-class probability per record")
    if not np.isfinite(probabilities).all() or ((probabilities < 0) | (probabilities > 1)).any():
        raise ValueError("Probabilities must be finite values in [0,1]")
    return probabilities


def _envelope(entity, context, metric_id, value, details, reason=None):
    _validate(entity, context)
    objective = next(item for item in CONTRACT["objectives"] if item["metric"]["id"] == metric_id)
    metric = objective["metric"]
    threshold = objective["condition"]["threshold"]
    if value is not None:
        if not math.isfinite(value) or not metric["range"]["lower"] <= value <= metric["range"]["upper"]:
            raise ValueError(f"{metric_id} value is outside its catalog range")
    determinate = value is not None and reason is None
    if determinate:
        operator = threshold["operator"]
        if operator not in ("GEQ", "LEQ"):
            raise ValueError(f"Unsupported condition operator: {operator}")
        passed = value >= threshold["value"] if operator == "GEQ" else value <= threshold["value"]
        status = "pass" if passed else "fail"
    else:
        if not reason:
            raise ValueError("An inconclusive measurement requires an explicit reason")
        status = "inconclusive"
    source_path, source_hash = CONTRACT["grounding"][metric_id]
    computed_at = context.get("measured_at") or datetime.now(timezone.utc).isoformat()
    return {
        "project": entity["project"],
        "entity": entity["entity"],
        "entity_version": entity["version"],
        "objective_ref": f"model:{entity['entity']}#{metric_id}",
        "objective": objective,
        "metric_result": {
            "metric": metric, "value": value, "computed_at": computed_at,
        } if determinate else None,
        "status": "SUCCESS" if determinate else "INCOMPLETE",
        "error": reason,
        "evidence": {
            "details": details,
            "assessment": {
                "status": status, "determinate": determinate, "reason": reason,
                "operator": threshold["operator"], "threshold": threshold["value"],
                "observed_value": value,
            },
        },
        "provenance": {
            "computation_source": source_path, "computation_source_hash": source_hash,
            "bundle_version": CONTRACT["bundle_version"],
            "specification_extension": CONTRACT["extension_key"],
            "specification_model_key": CONTRACT["specification_model_key"],
            "model_key": entity["key"],
            "dataset_key": context["dataset_key"], "run_key": context["run_key"],
            "dataset_evidence_available": bool(context.get("training_evidence") or "train" in context),
            "decision_threshold": DECISION_THRESHOLD,
            "protocol": "historical-approval-v1",
            "implementation_sha256": context["implementation_sha256"],
            "measurement_source": context.get("measurement_source", "model-and-dataset computation"),
            "target_semantics": "Historical approval, not repayment/default risk",
        },
    }


def _slices(context):
    train, test = context["train"], context["test"]
    required = {"Gender", "Age", "Annual_Income"}
    missing = required.difference(train.columns.intersection(test.columns))
    if missing:
        raise ValueError(f"Missing approved audit attributes: {sorted(missing)}")
    age = pd.to_numeric(test["Age"], errors="raise")
    train_age = pd.to_numeric(train["Age"], errors="raise")
    income = pd.to_numeric(test["Annual_Income"], errors="raise")
    train_income = pd.to_numeric(train["Annual_Income"], errors="raise")
    for values in (age, train_age, income, train_income):
        if not np.isfinite(values.dropna().to_numpy(dtype=float)).all():
            raise ValueError("Audit attributes must be finite when present")
    for values in (age, train_age):
        if (values.dropna() < 0).any() or (values.dropna() > 120).any():
            raise ValueError("Age must be within [0,120]")
    if (income.dropna() < 0).any() or (train_income.dropna() < 0).any():
        raise ValueError("Annual_Income must be nonnegative")
    edges = train_income.dropna().quantile([1 / 3, 2 / 3]).to_numpy(dtype=float)
    income_available = len(edges) == 2 and np.isfinite(edges).all() and edges[0] < edges[1]
    # Prefix observed values so a real category cannot collide with the missing-group label.
    gender = test["Gender"].map(lambda item: "missing" if pd.isna(item) else f"value:{item}")
    training_gender = train["Gender"].map(lambda item: "missing" if pd.isna(item) else f"value:{item}")
    age_band = pd.Series(
        np.select(
            [age.isna().to_numpy(), age.lt(30).fillna(False).to_numpy(dtype=bool),
             age.lt(60).fillna(False).to_numpy(dtype=bool)],
            ["missing", "<30", "30-59"], default=">=60",
        ),
        index=test.index,
    )
    if income_available:
        income_band = pd.Series(
            np.select(
                [income.isna().to_numpy(), income.le(edges[0]).fillna(False).to_numpy(dtype=bool),
                 income.le(edges[1]).fillna(False).to_numpy(dtype=bool)],
                ["missing", "low", "middle"], default="high",
            ), index=test.index,
        )
    else:
        income_band = pd.Series("undefined-tertiles", index=test.index)
    slices = pd.DataFrame({"Gender": gender, "age_band": age_band, "income_band": income_band})
    for name, other in (("gender_age", age_band), ("gender_income", income_band)):
        slices[name] = [json.dumps(pair) for pair in zip(gender, other)]
    return slices, {
        "income_tertile_edges": edges.tolist() if income_available else None,
        "income_tertiles_available": bool(income_available),
        "minimum_positives": MIN_CLASS_SUPPORT, "minimum_negatives": MIN_CLASS_SUPPORT,
        "intersections": "diagnostic only",
        "expected_main_groups": {
            "Gender": sorted(set(gender).union(training_gender)),
            "age_band": ["<30", "30-59", ">=60"] + (
                ["missing"] if age.isna().any() or train_age.isna().any() else []
            ),
            "income_band": ["low", "middle", "high"] + (
                ["missing"] if income.isna().any() or train_income.isna().any() else []
            ),
        },
    }


def _slice_groups(slices, protocol, name):
    return protocol["expected_main_groups"][name] if name in MAIN_SLICES else sorted(slices[name].unique())


def _ece(labels, probabilities):
    bins = np.minimum((probabilities * 10).astype(int), 9)
    details = []
    value = 0.0
    for number in range(10):
        mask = bins == number
        count = int(mask.sum())
        observed = float(labels[mask].mean()) if count else None
        predicted = float(probabilities[mask].mean()) if count else None
        if count:
            value += count / len(labels) * abs(observed - predicted)
        details.append({
            "lower": number / 10, "upper": (number + 1) / 10,
            "upper_inclusive": number == 9, "count": count,
            "observed_frequency": observed, "mean_probability": predicted,
        })
    return float(value), details


def evaluate_auc(entity, context):
    _validate(entity, context)
    labels = context["test"]["Loan_Approval_Status"].to_numpy(dtype=int)
    probabilities = _probabilities(entity, context["test"], context)
    if len(np.unique(labels)) < 2:
        return _envelope(entity, context, "metric-auc-roc", None, {}, "Held-out labels contain only one class")
    slices, protocol = _slices(context)
    subgroup_results = {}
    for name in ALL_SLICES:
        subgroup_results[name] = {}
        for group in _slice_groups(slices, protocol, name):
            mask = (slices[name] == group).to_numpy()
            enough = min(int((labels[mask] == 0).sum()), int((labels[mask] == 1).sum())) >= MIN_CLASS_SUPPORT
            subgroup_results[name][group] = {
                "count": int(mask.sum()),
                "value": float(roc_auc_score(labels[mask], probabilities[mask])) if enough else None,
                "status": "measured" if enough else "inconclusive: insufficient class support",
            }
    return _envelope(entity, context, "metric-auc-roc", float(roc_auc_score(labels, probabilities)),
                     {"subgroups": subgroup_results, "protocol": protocol})


def evaluate_fairness(entity, context):
    _validate(entity, context)
    labels = context["test"]["Loan_Approval_Status"].to_numpy(dtype=int)
    predictions = (_probabilities(entity, context["test"], context) >= DECISION_THRESHOLD).astype(int)
    slices, protocol = _slices(context)
    results, main_gaps, incomplete = {}, [], []
    for name in ALL_SLICES:
        groups, tprs, fprs, supported = {}, [], [], True
        for group in _slice_groups(slices, protocol, name):
            mask = (slices[name] == group).to_numpy()
            group_labels, group_predictions = labels[mask], predictions[mask]
            tn, fp, fn, tp = [
                int(((group_labels == actual) & (group_predictions == predicted)).sum())
                for actual, predicted in ((0, 0), (0, 1), (1, 0), (1, 1))
            ]
            positives, negatives = tp + fn, tn + fp
            enough = positives >= MIN_CLASS_SUPPORT and negatives >= MIN_CLASS_SUPPORT
            groups[group] = {
                "tn": tn, "fp": fp, "fn": fn, "tp": tp,
                "positives": positives, "negatives": negatives,
                "tpr": tp / positives if positives else None,
                "fpr": fp / negatives if negatives else None,
                "sufficient_support": enough,
            }
            if enough:
                tprs.append(tp / positives)
                fprs.append(fp / negatives)
            else:
                supported = False
        supported = supported and len(groups) >= 2
        if "income" in name and not protocol["income_tertiles_available"]:
            supported = False
        gap = max(max(tprs) - min(tprs), max(fprs) - min(fprs)) if supported else None
        results[name] = {"groups": groups, "equalized_odds_difference": gap}
        if name in MAIN_SLICES:
            if gap is None:
                incomplete.append(name)
            else:
                main_gaps.append(gap)
    value = float(max(main_gaps)) if not incomplete else None
    reason = f"Unsupported main slices: {', '.join(incomplete)}" if incomplete else None
    return _envelope(entity, context, "metric-equalized-odds-difference", value,
                     {"slices": results, "protocol": protocol}, reason)


def evaluate_calibration(entity, context):
    _validate(entity, context)
    labels = context["test"]["Loan_Approval_Status"].to_numpy(dtype=int)
    probabilities = _probabilities(entity, context["test"], context)
    value, bins = _ece(labels, probabilities)
    slices, protocol = _slices(context)
    groups = {}
    for name in ALL_SLICES:
        groups[name] = {}
        for group in _slice_groups(slices, protocol, name):
            mask = (slices[name] == group).to_numpy()
            group_value, group_bins = _ece(labels[mask], probabilities[mask]) if mask.any() else (None, [])
            enough = min(int((labels[mask] == 0).sum()), int((labels[mask] == 1).sum())) >= MIN_CLASS_SUPPORT
            groups[name][group] = {
                "value": group_value, "bins": group_bins,
                "status": "diagnostic" if enough else "inconclusive: insufficient class support",
            }
    return _envelope(entity, context, "metric-expected-calibration-error", value,
                     {"bins": bins, "subgroups": groups, "protocol": protocol,
                      "semantics": "Calibration of historical approval probabilities only"})


def evaluate_explanations(entity, context):
    _validate(entity, context)
    pipeline = entity["estimator"]
    preprocessor = pipeline.named_steps["preprocessor"]
    train = context["train"][context["feature_columns"]]
    test = context["test"][context["feature_columns"]]
    x_train, x_test = preprocessor.transform(train), preprocessor.transform(test)
    train_predictions = (_probabilities(entity, context["train"], context) >= DECISION_THRESHOLD).astype(int)
    test_predictions = (_probabilities(entity, context["test"], context) >= DECISION_THRESHOLD).astype(int)
    surrogate = DecisionTreeClassifier(max_depth=5, min_samples_leaf=10, random_state=42)
    surrogate.fit(x_train, train_predictions)
    train_leaves, test_leaves = surrogate.apply(x_train), surrogate.apply(x_test)
    support = np.bincount(train_leaves, minlength=surrogate.tree_.node_count)
    coverage = float((support[test_leaves] >= 10).mean())
    feature_names = preprocessor.get_feature_names_out().tolist()
    original_fields = []
    for name, transformer, columns in preprocessor.transformers_:
        if name == "remainder":
            continue
        if name == "numeric":
            imputed = transformer.named_steps["imputer"].get_feature_names_out(columns)
            original_fields.extend(
                item.removeprefix("missingindicator_") if item not in columns else item for item in imputed
            )
        elif name == "categorical":
            encoder = transformer.named_steps["one_hot"]
            original_fields.extend(
                column for column, categories in zip(columns, encoder.categories_) for _ in categories
            )
        else:
            raise ValueError(f"Unsupported preprocessor transformer: {name}")
    if len(original_fields) != len(feature_names):
        raise ValueError("Cannot map transformed explanation features to original fields")
    tree = surrogate.tree_
    fidelity = float(accuracy_score(test_predictions, surrogate.predict(x_test)))
    details = {
        "covered": int((support[test_leaves] >= 10).sum()), "total": len(test),
        "surrogate_fidelity": fidelity,
        "fidelity_acceptance": "not specified; diagnostic only",
        "reviewer_availability": "unverified", "override_escalation": "unverified",
        "coverage_scope": "offline catalog surrogate-support proxy, not verified human-review access",
        "transformed_feature_mapping": dict(zip(feature_names, original_fields)),
        "tree": {
            "children_left": tree.children_left.tolist(), "children_right": tree.children_right.tolist(),
            "feature": tree.feature.tolist(), "threshold": tree.threshold.tolist(),
            "class_counts": tree.value.tolist(), "classes": surrogate.classes_.tolist(),
            "training_leaf_support": support.tolist(), "feature_names": feature_names,
        },
        "prediction_traces": [
            {"row_id": int(row), "leaf": int(leaf), "support": int(support[leaf])}
            for row, leaf in zip(test.index, test_leaves)
        ],
        "settings": {"max_depth": 5, "min_samples_leaf": 10, "random_state": 42},
    }
    return _envelope(entity, context, "metric-decision-coverage", coverage, details)


def evaluate_membership(entity, context):
    _validate(entity, context)
    rng = np.random.default_rng(42)
    count = min(len(context["train"]), len(context["test"]))
    if count < 4:
        return _envelope(entity, context, "metric-membership-inference-auc", None, {},
                         "At least four members and four non-members are required for an attack split")
    members = context["train"].iloc[rng.choice(len(context["train"]), count, replace=False)]
    nonmembers = context["test"].iloc[rng.choice(len(context["test"]), count, replace=False)]
    attack_frames = pd.concat([members, nonmembers])
    probabilities = _probabilities(entity, attack_frames, context)
    labels = attack_frames["Loan_Approval_Status"].to_numpy(dtype=int)
    true_probability = np.where(labels == 1, probabilities, 1 - probabilities)
    features = np.column_stack([
        -np.log(np.clip(true_probability, np.finfo(float).eps, 1)),
        np.maximum(probabilities, 1 - probabilities), np.minimum(probabilities, 1 - probabilities),
    ])
    membership = np.concatenate([np.ones(count, dtype=int), np.zeros(count, dtype=int)])
    train_ids, test_ids = train_test_split(
        np.arange(2 * count), test_size=0.5, stratify=membership, random_state=42,
    )
    attacker = LogisticRegression(max_iter=1000, random_state=42)
    attacker.fit(features[train_ids], membership[train_ids])
    train_scores = attacker.predict_proba(features[train_ids])[:, list(attacker.classes_).index(1)]
    orientation = -1 if roc_auc_score(membership[train_ids], train_scores) < 0.5 else 1
    scores = attacker.predict_proba(features[test_ids])[:, list(attacker.classes_).index(1)]
    if orientation == -1:
        scores = 1 - scores
    raw_auc = float(roc_auc_score(membership[test_ids], scores))
    bootstraps = []
    for _ in range(200):
        sample = np.concatenate([
            rng.choice(np.flatnonzero(membership[test_ids] == label),
                       int((membership[test_ids] == label).sum()), replace=True)
            for label in (0, 1)
        ])
        bootstraps.append(float(roc_auc_score(membership[test_ids][sample], scores[sample])))
    details = {
        "raw_attack_test_auc": raw_auc, "score_orientation": orientation,
        "bootstrap_95_percent_interval": np.quantile(bootstraps, [0.025, 0.975]).tolist(),
        "bootstrap_resamples": 200,
        "members": count, "nonmembers": count,
        "attack_train_rows": len(train_ids), "attack_test_rows": len(test_ids),
        "attacker_features": ["negative_log_likelihood", "maximum_probability", "minimum_probability"],
        "attacker": {"algorithm": "LogisticRegression", "max_iter": 1000, "random_state": 42},
        "partitions": {
            "attack_train": attack_frames.index[train_ids].tolist(),
            "attack_test": attack_frames.index[test_ids].tolist(),
            "member_rows": members.index.tolist(), "nonmember_rows": nonmembers.index.tolist(),
        },
        "limitations": "One black-box attack; not a privacy guarantee",
    }
    # The catalog range starts at chance; do not flip scores using attack-test labels.
    if raw_auc < 0.5:
        return _envelope(entity, context, "metric-membership-inference-auc", None, details,
                         "Attack-test AUC is below the catalog range; raw estimate retained without test-label reorientation")
    return _envelope(entity, context, "metric-membership-inference-auc", raw_auc, details)


def evaluate_robustness(entity, context):
    _validate(entity, context)
    return _envelope(
        entity, context, "metric-adversarial-accuracy", None,
        {"required_protocol_fields": [
            "mutable_fields", "per_field_bounds_and_budgets", "search_method_and_budget",
            "label_preservation_justification", "validity_checks", "random_seed",
        ]},
        "No approved tabular attack protocol supplied; adversarial accuracy was not computed",
    )


def evaluate_saved_metric(entity, context, metric_id, metric_name):
    """Assess one provenance-bound training measurement without requiring dataset access."""
    snapshot = context.get("training_evidence")
    if not snapshot:
        return _envelope(entity, context, metric_id, None, {},
                         "The model has no provenance-bound training measurements; retraining is required")
    statistics = snapshot["statistics"]
    value = context["model_metrics"].get(metric_name)
    if metric_id == "metric-equalized-odds-difference":
        details = {"slices": statistics["slices"], "income_tertile_edges": statistics["income_tertile_edges"]}
    elif metric_id == "metric-expected-calibration-error":
        details = {"bins": statistics["calibration_bins"],
                   "subgroup_calibration": "Requires the optional training dataset"}
    else:
        details = {"subgroup_statistics": statistics["slices"]}
    reason = None
    if value is None:
        reason = statistics.get("fairness_unavailable") or f"No saved {metric_name} measurement"
    return _envelope(entity, context, metric_id, value, details, reason)


"""Independent DH project function: model measurements -> compliance reports."""

import hashlib
import json
import logging
import tempfile
from pathlib import Path

import joblib
import numpy as np
import pandas as pd



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
            "objective_ref": measurement["objective_ref"], "status": measurement["status"],
            "error": measurement["error"], 
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