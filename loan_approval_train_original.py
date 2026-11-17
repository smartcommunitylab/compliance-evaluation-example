import json
import tempfile
from pathlib import Path

import joblib
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
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler


TARGET = "Loan_Approval_Status"
EXCLUDED_FEATURES = {"Applicant_ID", "Gender", "Age"}
MODEL_NAME = "loan-approval-classifier"


def train_loan_approval(project, run, loan_data):
    """Train and register a loan approval classifier from a DigitalHub Dataitem."""
    frame = loan_data.as_df()
    if not isinstance(frame, pd.DataFrame):
        raise TypeError("loan_data.as_df() must return a pandas DataFrame")
    if TARGET not in frame.columns:
        raise ValueError(f"Required target column {TARGET!r} is missing")

    frame = frame.dropna(subset=[TARGET]).copy()
    labels = frame[TARGET]
    classes = set(labels.unique())
    if classes != {0, 1}:
        raise ValueError(f"{TARGET} must contain both binary labels 0 and 1; found {classes}")
    if labels.value_counts().min() < 2:
        raise ValueError("At least two rows per target class are required for a stratified split")

    excluded = EXCLUDED_FEATURES.intersection(frame.columns)
    features = frame.drop(columns=[TARGET, *excluded])
    if features.empty:
        raise ValueError("No predictor columns remain after excluding target and identifier/protected fields")

    numeric_columns = features.select_dtypes(include=["number", "bool"]).columns.tolist()
    categorical_columns = [column for column in features.columns if column not in numeric_columns]
    transformers = []
    if numeric_columns:
        transformers.append(
            (
                "numeric",
                Pipeline(
                    [
                        ("imputer", SimpleImputer(strategy="median", add_indicator=True)),
                        ("scaler", StandardScaler()),
                    ]
                ),
                numeric_columns,
            )
        )
    if categorical_columns:
        transformers.append(
            (
                "categorical",
                Pipeline(
                    [
                        ("imputer", SimpleImputer(strategy="constant", fill_value="__missing__")),
                        ("one_hot", OneHotEncoder(handle_unknown="ignore")),
                    ]
                ),
                categorical_columns,
            )
        )

    classifier_parameters = {"class_weight": "balanced", "max_iter": 1000, "random_state": 42}
    pipeline = Pipeline(
        [
            ("preprocessor", ColumnTransformer(transformers=transformers)),
            ("classifier", LogisticRegression(**classifier_parameters)),
        ]
    )
    x_train, x_test, y_train, y_test = train_test_split(
        features,
        labels,
        test_size=0.2,
        random_state=42,
        stratify=labels,
    )
    pipeline.fit(x_train, y_train)

    predictions = pipeline.predict(x_test)
    positive_class_index = list(pipeline.classes_).index(1)
    approval_probabilities = pipeline.predict_proba(x_test)[:, positive_class_index]
    metrics = {
        "accuracy": float(accuracy_score(y_test, predictions)),
        "precision": float(precision_score(y_test, predictions, pos_label=1, zero_division=0)),
        "recall": float(recall_score(y_test, predictions, pos_label=1, zero_division=0)),
        "f1": float(f1_score(y_test, predictions, pos_label=1, zero_division=0)),
        "roc_auc": float(roc_auc_score(y_test, approval_probabilities)),
        "train_rows": int(len(x_train)),
        "test_rows": int(len(x_test)),
    }
    for metric_name, value in metrics.items():
        run.log_metric(metric_name, value)

    with tempfile.TemporaryDirectory() as temporary_directory:
        model_path = Path(temporary_directory) / "loan_approval_classifier.joblib"
        joblib.dump(pipeline, model_path)
        model = project.log_sklearn(
            name=MODEL_NAME,
            source=str(model_path),
            algorithm="LogisticRegression",
            parameters=classifier_parameters,
        )
        model.log_metrics(metrics)
        project.log_dataitem(
            name="loan-approval-metrics",
            kind="table",
            data=pd.DataFrame(
                [
                    {
                        **metrics,
                        "confusion_matrix": json.dumps(
                            confusion_matrix(y_test, predictions, labels=[0, 1]).tolist()
                        ),
                        "model": MODEL_NAME,
                    }
                ]
            ),
        )

    return {
        "model": MODEL_NAME,
        "metrics": metrics,
        "algorithm": "LogisticRegression",
        "confusion_matrix": [
            [int(value) for value in row]
            for row in confusion_matrix(y_test, predictions, labels=[0, 1])
        ],
        "excluded_features": sorted(excluded),
    }