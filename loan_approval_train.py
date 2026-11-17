"""Self-contained training handler: measurements only, no compliance decisions."""

import hashlib
import json
import logging
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import FixedThresholdClassifier, train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler


TARGET = "Loan_Approval_Status"
EXCLUDED_FEATURES = {"Applicant_ID", "Gender", "Age", "Credit_Score", "Default_Risk"}
MODEL_NAME = "loan-approval-classifier"
DECISION_THRESHOLD = 0.90
LOGGER = logging.getLogger(__name__)


def dataset_fingerprint(frame):
    """Bind persisted split positions to the exact input rows, order and schema."""
    digest = hashlib.sha256()
    digest.update(json.dumps(
        [(str(column), str(dtype)) for column, dtype in frame.dtypes.items()]
    ).encode())
    digest.update(pd.util.hash_pandas_object(frame, index=False).to_numpy().tobytes())
    return digest.hexdigest()


def training_measurements(train, test, probabilities):
    """Return additional numeric measurements and their supporting statistics."""
    probabilities = np.asarray(probabilities, dtype=float)
    if test.empty or probabilities.shape != (len(test),):
        raise ValueError("Nonempty test records require one probability per row")
    if not np.isfinite(probabilities).all() or ((probabilities < 0) | (probabilities > 1)).any():
        raise ValueError("Probabilities must be finite values in [0,1]")
    labels = test[TARGET].to_numpy(dtype=int)
    predictions = (probabilities >= DECISION_THRESHOLD).astype(int)
    bins = np.minimum((probabilities * 10).astype(int), 9)
    bin_statistics, ece = [], 0.0
    for number in range(10):
        mask = bins == number
        count = int(mask.sum())
        observed = float(labels[mask].mean()) if count else None
        predicted = float(probabilities[mask].mean()) if count else None
        if count:
            ece += count / len(test) * abs(observed - predicted)
        bin_statistics.append({
            "lower": number / 10, "upper": (number + 1) / 10,
            "upper_inclusive": number == 9, "count": count,
            "observed_frequency": observed, "mean_probability": predicted,
        })
    numeric = {"expected_calibration_error": float(ece)}
    details = {"calibration_bins": bin_statistics, "slices": {}, "income_tertile_edges": None}
    needed = {"Gender", "Age", "Annual_Income"}
    if not needed.issubset(train.columns.intersection(test.columns)):
        details["fairness_unavailable"] = f"Missing audit attributes: {sorted(needed.difference(test.columns))}"
        LOGGER.warning(details["fairness_unavailable"])
        return numeric, details
    age = pd.to_numeric(test["Age"], errors="raise")
    training_age = pd.to_numeric(train["Age"], errors="raise")
    income = pd.to_numeric(test["Annual_Income"], errors="raise")
    training_income = pd.to_numeric(train["Annual_Income"], errors="raise")
    for values in (age, training_age, income, training_income):
        if not np.isfinite(values.dropna().to_numpy(dtype=float)).all():
            raise ValueError("Audit attributes must be finite when present")
    for values in (age, training_age):
        if not values.dropna().between(0, 120).all():
            raise ValueError("Age must be within [0,120]")
    if (income.dropna() < 0).any() or (training_income.dropna() < 0).any():
        raise ValueError("Annual_Income must be nonnegative")
    gender = test["Gender"].map(lambda item: "missing" if pd.isna(item) else f"value:{item}")
    training_gender = train["Gender"].map(lambda item: "missing" if pd.isna(item) else f"value:{item}")
    age_bands = pd.Series(np.select(
        [age.isna().to_numpy(), age.lt(30).fillna(False).to_numpy(dtype=bool),
         age.lt(60).fillna(False).to_numpy(dtype=bool)],
        ["missing", "<30", "30-59"], default=">=60"
    ), index=test.index)
    edges = training_income.dropna().quantile([1 / 3, 2 / 3]).to_numpy(dtype=float)
    valid_edges = bool(np.isfinite(edges).all() and edges[0] < edges[1])
    if valid_edges:
        details["income_tertile_edges"] = edges.tolist()
        income_bands = pd.Series(np.select(
            [income.isna().to_numpy(), income.le(edges[0]).fillna(False).to_numpy(dtype=bool),
             income.le(edges[1]).fillna(False).to_numpy(dtype=bool)],
            ["missing", "low", "middle"], default="high",
        ), index=test.index)
    else:
        income_bands = pd.Series("undefined-tertiles", index=test.index)
    slices = {
        "Gender": gender, "age_band": age_bands, "income_band": income_bands,
        "gender_age": pd.Series([json.dumps(pair) for pair in zip(gender, age_bands)], index=test.index),
        "gender_income": pd.Series([json.dumps(pair) for pair in zip(gender, income_bands)], index=test.index),
    }
    expected = {
        "Gender": sorted(set(gender).union(training_gender)),
        "age_band": ["<30", "30-59", ">=60"] + (
            ["missing"] if age.isna().any() or training_age.isna().any() else []
        ),
        "income_band": ["low", "middle", "high"] + (
            ["missing"] if income.isna().any() or training_income.isna().any() else []
        ),
    }
    gaps, incomplete = [], []
    for name, groups in slices.items():
        group_statistics, tprs, fprs, supported = {}, [], [], True
        for group in expected.get(name, sorted(groups.unique())):
            mask = (groups == group).to_numpy()
            group_labels, group_predictions = labels[mask], predictions[mask]
            tn, fp, fn, tp = [
                int(((group_labels == actual) & (group_predictions == predicted)).sum())
                for actual, predicted in ((0, 0), (0, 1), (1, 0), (1, 1))
            ]
            positives, negatives = tp + fn, tn + fp
            enough = positives >= 30 and negatives >= 30
            group_statistics[group] = {
                "tn": tn, "fp": fp, "fn": fn, "tp": tp,
                "positives": positives, "negatives": negatives,
                "tpr": tp / positives if positives else None,
                "fpr": fp / negatives if negatives else None,
                "roc_auc": float(roc_auc_score(labels[mask], probabilities[mask])) if enough else None,
                "sufficient_support": enough,
            }
            if enough:
                tprs.append(tp / positives)
                fprs.append(fp / negatives)
            else:
                supported = False
        supported = supported and len(group_statistics) >= 2
        if "income" in name and not valid_edges:
            supported = False
        gap = float(max(max(tprs) - min(tprs), max(fprs) - min(fprs))) if supported else None
        details["slices"][name] = {"groups": group_statistics, "equalized_odds_difference": gap}
        if name in expected:
            if gap is None:
                incomplete.append(name)
            else:
                gaps.append(gap)
                numeric[f"equalized_odds_difference_{name.lower()}"] = gap
    if not incomplete:
        numeric["equalized_odds_difference"] = float(max(gaps))
    else:
        details["fairness_unavailable"] = f"Insufficient group support or undefined tertiles: {incomplete}"
        LOGGER.warning(details["fairness_unavailable"])
    return numeric, details


def train_loan_approval(project, run, loan_data):
    """Train and register a historical-approval classifier from a DigitalHub Dataitem."""
    frame = loan_data.as_df()
    if not isinstance(frame, pd.DataFrame):
        raise TypeError("loan_data.as_df() must return a pandas DataFrame")
    if TARGET not in frame.columns or not frame.columns.is_unique:
        raise ValueError(f"Unique dataset columns including {TARGET} are required")
    frame = frame.reset_index(drop=True)
    fingerprint = dataset_fingerprint(frame)
    if "Applicant_ID" in frame and (
        frame["Applicant_ID"].isna().any() or frame["Applicant_ID"].duplicated().any()
    ):
        raise ValueError("Applicant_ID must be non-null and unique to prevent applicant leakage")
    dropped_labels = int(frame[TARGET].isna().sum())
    if dropped_labels:
        LOGGER.warning("Excluding %d records with missing %s", dropped_labels, TARGET)
    frame = frame.dropna(subset=[TARGET]).copy()
    labels = frame[TARGET]
    if set(labels.unique()) != {0, 1}:
        raise ValueError(f"{TARGET} must contain both binary labels 0 and 1")
    if labels.value_counts().min() < 2:
        raise ValueError("At least two rows per class are required for a stratified split")
    excluded = EXCLUDED_FEATURES.intersection(frame.columns)
    features = frame.drop(columns=[TARGET, *excluded])
    if features.empty:
        raise ValueError("No predictors remain after excluding target and restricted fields")
    numeric_columns = features.select_dtypes(include=["number", "bool"]).columns.tolist()
    categorical_columns = [column for column in features.columns if column not in numeric_columns]
    transformers = []
    if numeric_columns:
        transformers.append(("numeric", Pipeline([
            ("imputer", SimpleImputer(strategy="median", add_indicator=True, keep_empty_features=True)),
            ("scaler", StandardScaler()),
        ]), numeric_columns))
    if categorical_columns:
        transformers.append(("categorical", Pipeline([
            ("imputer", SimpleImputer(
                missing_values=pd.NA, strategy="constant",
                fill_value="__missing__", keep_empty_features=True,
            )),
            ("one_hot", OneHotEncoder(handle_unknown="ignore")),
        ]), categorical_columns))
    classifier_parameters = {"class_weight": "balanced", "max_iter": 1000, "random_state": 42}
    pipeline = Pipeline([
        ("preprocessor", ColumnTransformer(transformers=transformers)),
        ("classifier", FixedThresholdClassifier(
            LogisticRegression(**classifier_parameters),
            threshold=DECISION_THRESHOLD, response_method="predict_proba",
        )),
    ])
    x_train, x_test, y_train, y_test = train_test_split(
        features, labels, test_size=0.2, random_state=42, stratify=labels,
    )
    if set(y_test.unique()) != {0, 1} or set(y_train.unique()) != {0, 1}:
        raise ValueError("Both classes must be represented in each partition")
    pipeline.fit(x_train, y_train)
    predictions = pipeline.predict(x_test)
    positive_class_index = list(pipeline.classes_).index(1)
    probabilities = pipeline.predict_proba(x_test)[:, positive_class_index]
    metrics = {
        "accuracy": float(accuracy_score(y_test, predictions)),
        "precision": float(precision_score(y_test, predictions, pos_label=1, zero_division=0)),
        "recall": float(recall_score(y_test, predictions, pos_label=1, zero_division=0)),
        "f1": float(f1_score(y_test, predictions, pos_label=1, zero_division=0)),
        "roc_auc": float(roc_auc_score(y_test, probabilities)),
        "train_rows": len(x_train), "test_rows": len(x_test),
        "decision_threshold": DECISION_THRESHOLD, "missing_label_rows": dropped_labels,
    }
    additional, statistics = training_measurements(
        frame.loc[x_train.index], frame.loc[x_test.index], probabilities,
    )
    metrics.update(additional)
    evidence = {
        "protocol": "historical-approval-v1", "target": TARGET, "positive_label": 1,
        "target_semantics": "Historical approval, not repayment/default risk",
        "decision_threshold": DECISION_THRESHOLD,
        "dataset_key": loan_data.key, "dataset_fingerprint": fingerprint,
        "run_key": run.key, "measured_at": datetime.now(timezone.utc).isoformat(),
        "feature_columns": features.columns.tolist(), "excluded_features": sorted(EXCLUDED_FEATURES),
        "train_row_ids": x_train.index.tolist(), "test_row_ids": x_test.index.tolist(),
        "split": {"test_size": 0.2, "random_state": 42, "stratify": TARGET},
        "metrics_snapshot": metrics, "statistics": statistics,
        "libraries": {"pandas": pd.__version__, "numpy": np.__version__},
        "confusion_matrix": confusion_matrix(y_test, predictions, labels=[0, 1]).tolist(),
    }
    for metric_name, value in metrics.items():
        run.log_metric(metric_name, value)
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "loan_approval_classifier.joblib"
        joblib.dump(pipeline, path)
        evidence["model_sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
        try:
            model = project.log_sklearn(
                name=MODEL_NAME, source=str(path), algorithm="LogisticRegression",
                parameters={**classifier_parameters, "training_evidence": evidence},
            )
        except Exception:
            LOGGER.exception("Failed to register the trained model and its evidence")
            raise
        model.log_metrics(metrics)
        project.log_dataitem(
            name="loan-approval-metrics", kind="table",
            data=pd.DataFrame([{
                **metrics, "confusion_matrix": json.dumps(evidence["confusion_matrix"]),
                "model": MODEL_NAME, "model_key": model.key, "dataset_key": loan_data.key,
                "statistics": json.dumps(statistics, allow_nan=False),
            }]),
        )
    return {
        "model": MODEL_NAME, "model_key": model.key, "metrics": metrics,
        "algorithm": "LogisticRegression", "confusion_matrix": evidence["confusion_matrix"],
        "excluded_features": sorted(excluded),
    }
