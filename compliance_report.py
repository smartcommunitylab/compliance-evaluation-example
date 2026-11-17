"""Self-contained compliance evaluation and EVALUATION/TEST report publication.

Generated from the combined report template. ``run(project, entity, **kwargs)`` runs every embedded
metric evaluator on ``entity`` (the analyzed DigitalHub DataItem or Model), builds the OKF reports and
saves them on the entity as named ``compliance-report`` extensions, replacing existing ones.
Additional keyword arguments are passed to every evaluator that accepts them.
"""
from __future__ import annotations

import inspect
import json
import operator
from typing import Any

# --- Embedded metric evaluators ---------------------------------------------------------------

from datetime import datetime, timezone
from time import perf_counter
from typing import Any
import pandas as pd

def evaluate_loan_completeness(entity: Any) -> dict:
    """Measure mean non-null completeness across every data-item column."""
    started = perf_counter()
    if not hasattr(entity, "as_df"):
        raise TypeError("entity must be a DigitalHub data item exposing as_df()")
    frame = entity.as_df()
    if not isinstance(frame, pd.DataFrame):
        raise TypeError("entity.as_df() must return a pandas DataFrame")
    if frame.empty or frame.shape[1] == 0:
        raise ValueError("Completeness requires a non-empty dataset with columns")
    per_column = 1.0 - frame.isnull().mean()
    value = float(per_column.mean())
    duration = perf_counter() - started
    return {"schema_version":"1.0","objective_ref":"dataset:loan_dataset#required-field-completeness","objective_snapshot":{"name":"Required-field completeness","description":"Measure non-null completeness for fields necessary to the risk-signal purpose, separately by gender, age band and socioeconomic proxy group; document and investigate differential missingness.","metric":{"id":"metric-data-completeness","name":"Dataset Completeness","description":"Fraction of required values that are present (non-null) in the dataset. A value ","kind":"PRIMITIVE","scale":"RATIO","unit":{"symbol":"%","name":"percent"},"range":{"lower":0.0,"upper":1.0,"discrete":False,"categories":None}},"condition":{"threshold":{"operator":"GEQ","value":0.95},"range":None,"categorical":None,"statistical":None}},"target":{"project":"loan-app3","entity_kind":"dataset","entity":"loan_dataset","version":"cyber-hawk"},"metric_result":{"metric_id":"metric-data-completeness","value":value,"unit":{"symbol":"%","name":"percent"},"range":{"lower":0.0,"upper":1.0},"details":{"scope":"all columns in the Dataitem DataFrame","row_count":int(len(frame)),"column_count":int(frame.shape[1]),"per_column_completeness":{str(column):float(rate) for column,rate in per_column.items()},"missing_values_by_column":{str(column):int(frame[column].isna().sum()) for column in frame.columns}}},"measured_at":datetime.now(timezone.utc).isoformat(),"computation_time_seconds":duration,"provenance":{"computation_source":"catalog/metrics/data-quality/completeness.md","computation_source_hash":"f0f19dc59d2f9bed718784f751bf6ba5961406eb909e1bfa656917da55a2269e","bundle_version":"2b1e8e044ee8"},"assessment":{"status":"pass" if value >= 0.95 else "fail","determinate":True,"operator":"GEQ","threshold":0.95,"observed_value":value}}


from datetime import datetime, timezone
from time import perf_counter
from typing import Any
import pandas as pd

def evaluate_loan_accuracy(entity: Any) -> dict:
    """Measure the fraction of loan rows passing the confirmed domain checks."""
    started = perf_counter()
    if not hasattr(entity, "as_df"):
        raise TypeError("entity must be a DigitalHub data item exposing as_df()")
    frame = entity.as_df()
    if not isinstance(frame, pd.DataFrame):
        raise TypeError("entity.as_df() must return a pandas DataFrame")
    if frame.empty:
        raise ValueError("Accuracy requires at least one dataset row")
    rules = {"Age":lambda value:pd.notna(value) and 20<=value<=80,"Annual_Income":lambda value:pd.notna(value) and value>=0,"Monthly_Expenses":lambda value:pd.notna(value) and value>=0,"Total_Existing_Loan_Amount":lambda value:pd.notna(value) and value>=0,"Outstanding_Debt":lambda value:pd.notna(value) and value>=0,"Loan_Amount_Requested":lambda value:pd.notna(value) and value>=0,"Loan_Term":lambda value:pd.notna(value) and value>0,"Default_Risk":lambda value:pd.notna(value) and 0<=value<=1,"Loan_Approval_Status":lambda value:pd.notna(value) and value in (0,1)}
    missing = [column for column in rules if column not in frame.columns]
    if missing:
        raise ValueError(f"Required rule columns are missing: {missing}")
    mask = pd.Series(True, index=frame.index)
    failures: dict[str, int] = {}
    for column, rule in rules.items():
        passed = frame[column].apply(rule).astype(bool)
        failures[column] = int((~passed).sum())
        mask &= passed
    value = float(mask.mean())
    duration = perf_counter() - started
    return {"schema_version":"1.0","objective_ref":"dataset:loan_dataset#field-and-target-accuracy","objective_snapshot":{"name":"Field and target accuracy","description":"Validate source fidelity and plausible domains: Age 0–120, nonnegative income/expense/debt/loan amounts, positive loan term, Default_Risk in [0,1], and Loan_Approval_Status in {0,1}; reconcile labels against authoritative records.","metric":{"id":"metric-data-accuracy","name":"Data Accuracy / Correctness Rate","description":"Fraction of data values that correctly represent the real-world entity they desc","kind":"PRIMITIVE","scale":"RATIO","unit":{"symbol":"%","name":"percent"},"range":{"lower":0.0,"upper":1.0,"discrete":False,"categories":None}},"condition":{"threshold":{"operator":"GEQ","value":0.99},"range":None,"categorical":None,"statistical":None}},"target":{"project":"loan-app3","entity_kind":"dataset","entity":"loan_dataset","version":"cyber-hawk"},"metric_result":{"metric_id":"metric-data-accuracy","value":value,"unit":{"symbol":"%","name":"percent"},"range":{"lower":0.0,"upper":1.0},"details":{"row_count":int(len(frame)),"rows_passing_all_rules":int(mask.sum()),"row_failures_by_rule":failures,"validation_rules":{"Age":"20 <= value <= 80","financial amount columns":"value >= 0","Loan_Term":"value > 0","Default_Risk":"0 <= value <= 1","Loan_Approval_Status":"value in {0, 1}"}}},"measured_at":datetime.now(timezone.utc).isoformat(),"computation_time_seconds":duration,"provenance":{"computation_source":"catalog/metrics/data-quality/accuracy-correctness.md","computation_source_hash":"b0ca808c565249d64814d2d11da39d7b6cd9c110ad48f76cc892876ea6ec68c8","bundle_version":"2b1e8e044ee8"},"assessment":{"status":"pass" if value>=0.99 else "fail","determinate":True,"operator":"GEQ","threshold":0.99,"observed_value":value}}


from datetime import datetime, timezone
from time import perf_counter
from typing import Any
import pandas as pd

def evaluate_loan_consistency(entity: Any) -> dict:
    """Measure rows satisfying the confirmed loan consistency constraints."""
    started = perf_counter()
    if not hasattr(entity, "as_df"):
        raise TypeError("entity must be a DigitalHub data item exposing as_df()")
    frame = entity.as_df()
    if not isinstance(frame, pd.DataFrame):
        raise TypeError("entity.as_df() must return a pandas DataFrame")
    if frame.empty:
        raise ValueError("Consistency requires at least one dataset row")
    columns = ["Default_Risk", "Loan_Approval_Status", "Annual_Income", "Monthly_Expenses", "Total_Existing_Loan_Amount", "Outstanding_Debt", "Loan_Amount_Requested"]
    missing = [column for column in columns if column not in frame.columns]
    if missing:
        raise ValueError(f"Required consistency columns are missing: {missing}")
    constraints = [frame["Default_Risk"].between(0, 1, inclusive="both").fillna(False), frame["Loan_Approval_Status"].isin([0, 1]), frame["Annual_Income"].ge(0).fillna(False), frame["Monthly_Expenses"].ge(0).fillna(False), frame["Total_Existing_Loan_Amount"].ge(0).fillna(False), frame["Outstanding_Debt"].ge(0).fillna(False), frame["Loan_Amount_Requested"].ge(0).fillna(False)]
    mask = pd.Series(True, index=frame.index)
    for constraint in constraints:
        mask &= constraint.astype(bool)
    value = float(mask.mean())
    duration = perf_counter() - started
    return {"schema_version":"1.0","objective_ref":"dataset:loan_dataset#cross-field-consistency","objective_snapshot":{"name":"Cross-field consistency","description":"Ensure at least 99% of records satisfy documented domain and cross-field checks, including risk-score bounds, binary status values, nonnegative financial amounts, and consistency between application outcomes and source records; do not assume approval status is an in-scope model target.","metric":{"id":"metric-data-consistency","name":"Data Consistency Rate","description":"Fraction of records that satisfy all defined cross-field and referential integri","kind":"PRIMITIVE","scale":"RATIO","unit":{"symbol":"%","name":"percent"},"range":{"lower":0.0,"upper":1.0,"discrete":False,"categories":None}},"condition":{"threshold":{"operator":"GEQ","value":0.99},"range":None,"categorical":None,"statistical":None}},"target":{"project":"loan-app3","entity_kind":"dataset","entity":"loan_dataset","version":"cyber-hawk"},"metric_result":{"metric_id":"metric-data-consistency","value":value,"unit":{"symbol":"%","name":"percent"},"range":{"lower":0.0,"upper":1.0},"details":{"row_count":int(len(frame)),"rows_satisfying_all_constraints":int(mask.sum()),"failed_rows":int((~mask).sum()),"constraints":["Default_Risk in [0, 1]","Loan_Approval_Status in {0, 1}","Annual_Income >= 0","Monthly_Expenses >= 0","Total_Existing_Loan_Amount >= 0","Outstanding_Debt >= 0","Loan_Amount_Requested >= 0"]}},"measured_at":datetime.now(timezone.utc).isoformat(),"computation_time_seconds":duration,"provenance":{"computation_source":"catalog/metrics/data-quality/consistency.md","computation_source_hash":"a2ceb63ae4be6da6e530475542ca03bd96a22dafc57bb52fc018c2c253d2f9c3","bundle_version":"2b1e8e044ee8"},"assessment":{"status":"pass" if value>=0.99 else "fail","determinate":True,"operator":"GEQ","threshold":0.99,"observed_value":value}}


from datetime import datetime, timezone
from time import perf_counter
from typing import Any
import pandas as pd

def evaluate_loan_label_balance(entity: Any) -> dict:
    """Measure balance of the approved binary historical label."""
    started = perf_counter()
    if not hasattr(entity, "as_df"):
        raise TypeError("entity must be a DigitalHub data item exposing as_df()")
    frame = entity.as_df()
    if not isinstance(frame, pd.DataFrame):
        raise TypeError("entity.as_df() must return a pandas DataFrame")
    if "Loan_Approval_Status" not in frame.columns:
        raise ValueError("Required label column 'Loan_Approval_Status' is missing")
    labels = frame["Loan_Approval_Status"]
    observed = labels.dropna()
    if observed.empty:
        raise ValueError("Cannot measure label balance: the label column has no values")
    if not observed.isin([0, 1]).all():
        raise ValueError("Loan_Approval_Status must contain only binary values 0 and 1")
    counts = observed.value_counts().reindex([0, 1], fill_value=0)
    ratio = float(counts.min() / counts.max())
    duration = perf_counter() - started
    return {"schema_version":"1.0","objective_ref":"dataset:loan_dataset#categorical-target-balance","objective_snapshot":{"name":"Categorical target balance","description":"If Loan_Approval_Status is confirmed as a permitted historical training/evaluation label (rather than a target that automates approvals), maintain a minority-to-majority label ratio of at least 0.1 and report the class counts. For a continuous Default_Risk target, assess its distribution separately.","metric":{"id":"metric-label-balance-ratio","name":"Label Balance Ratio","description":"Ratio of the minority class count to the majority class count in a classificatio","kind":"PRIMITIVE","scale":"RATIO","unit":{"symbol":"ratio","name":"minority/majority ratio"},"range":{"lower":0.0,"upper":1.0,"discrete":False,"categories":None}},"condition":{"threshold":{"operator":"GEQ","value":0.1},"range":None,"categorical":None,"statistical":None}},"target":{"project":"loan-app3","entity_kind":"dataset","entity":"loan_dataset","version":"cyber-hawk"},"metric_result":{"metric_id":"metric-label-balance-ratio","value":ratio,"unit":{"symbol":"ratio","name":"minority/majority ratio"},"range":{"lower":0.0,"upper":1.0},"details":{"label_column":"Loan_Approval_Status","class_counts":[{"label":int(label),"count":int(count)} for label,count in counts.items()],"labeled_rows":int(counts.sum()),"missing_label_rows":int(labels.isna().sum()),"label_role":"approved historical training/evaluation label"}},"measured_at":datetime.now(timezone.utc).isoformat(),"computation_time_seconds":duration,"provenance":{"computation_source":"catalog/metrics/data-quality/label-balance-ratio.md","computation_source_hash":"73f5291299a9f1428d8ba0c41f07b0bee96cf98375281777f246d750b2aa8c12","bundle_version":"2b1e8e044ee8"},"assessment":{"status":"pass" if ratio>=0.1 else "fail","determinate":True,"operator":"GEQ","threshold":0.1,"observed_value":ratio}}


from datetime import datetime, timezone
from time import perf_counter
from typing import Any
import pandas as pd

def evaluate_loan_k_anonymity(entity: Any, evaluation_context: dict | None = None) -> dict:
    """Measure k-anonymity for selected untransformed quasi-identifiers."""
    started = perf_counter()
    if not hasattr(entity, "as_df"):
        raise TypeError("entity must be a DigitalHub data item exposing as_df()")
    frame = entity.as_df()
    if not isinstance(frame, pd.DataFrame):
        raise TypeError("entity.as_df() must return a pandas DataFrame")
    if frame.empty:
        raise ValueError("k-anonymity requires at least one dataset row")
    context = evaluation_context or {}
    quasi_identifiers = context.get("quasi_identifier_columns", ["Age", "Gender", "City/Town"])
    if not isinstance(quasi_identifiers, (list, tuple)) or not quasi_identifiers:
        raise ValueError("quasi_identifier_columns must be a non-empty list or tuple")
    quasi_identifiers = list(quasi_identifiers)
    if len(set(quasi_identifiers)) != len(quasi_identifiers):
        raise ValueError("quasi_identifier_columns must not contain duplicates")
    if "Applicant_ID" in quasi_identifiers:
        raise ValueError("Applicant_ID must be excluded from quasi-identifiers")
    missing = [column for column in quasi_identifiers if column not in frame.columns]
    if missing:
        raise ValueError(f"Quasi-identifier columns are missing: {missing}")
    group_sizes = frame.groupby(quasi_identifiers, dropna=False, observed=True).size()
    if group_sizes.empty:
        raise ValueError("Cannot measure k-anonymity for an empty equivalence-class set")
    value = int(group_sizes.min())
    duration = perf_counter() - started
    return {"schema_version":"1.0","objective_ref":"dataset:loan_dataset#re-identification-risk-before-data-sharing","objective_snapshot":{"name":"Re-identification risk before data sharing","description":"After removing or isolating Applicant_ID and generalizing relevant quasi-identifiers (such as age and City/Town), require k-anonymity of at least 5 before external disclosure or other release; apply stricter access controls to the identifiable training table.","metric":{"id":"metric-k-anonymity","name":"k-Anonymity","description":"Minimum number of records that share the same quasi-identifier combination. k = ","kind":"PRIMITIVE","scale":"ORDINAL","unit":{"symbol":"k","name":"equivalence class size"},"range":{"lower":1.0,"upper":None,"discrete":True,"categories":None}},"condition":{"threshold":{"operator":"GEQ","value":5.0},"range":None,"categorical":None,"statistical":None}},"target":{"project":"loan-app3","entity_kind":"dataset","entity":"loan_dataset","version":"cyber-hawk"},"metric_result":{"metric_id":"metric-k-anonymity","value":value,"unit":{"symbol":"k","name":"equivalence class size"},"range":{"lower":1,"upper":None},"details":{"quasi_identifier_columns":quasi_identifiers,"applicant_id_excluded":True,"generalization_applied":False,"row_count":int(len(frame)),"equivalence_class_count":int(len(group_sizes)),"minimum_equivalence_class_size":value,"missing_quasi_identifier_values_grouped_together":True}},"measured_at":datetime.now(timezone.utc).isoformat(),"computation_time_seconds":duration,"provenance":{"computation_source":"catalog/metrics/privacy/k-anonymity.md","computation_source_hash":"9222d9d8fc43e6bd0936f45eb79ccc5d535bf8a97d760c139b56d92b3a4dbcf6","bundle_version":"2b1e8e044ee8"},"assessment":{"status":"pass" if value>=5 else "fail","determinate":True,"operator":"GEQ","threshold":5.0,"observed_value":value}}

# --- Objectives and reports -------------------------------------------------------------------

OBJECTIVES = {'dataset:loan_dataset#required-field-completeness': {'name': 'Required-field completeness',
                                                      'description': 'Measure non-null '
                                                                     'completeness for fields '
                                                                     'necessary to the risk-signal '
                                                                     'purpose, separately by '
                                                                     'gender, age band and '
                                                                     'socioeconomic proxy group; '
                                                                     'document and investigate '
                                                                     'differential missingness.',
                                                      'metric': {'id': 'metric-data-completeness',
                                                                 'name': 'Dataset Completeness',
                                                                 'description': 'Fraction of '
                                                                                'required values '
                                                                                'that are present '
                                                                                '(non-null) in the '
                                                                                'dataset. A value ',
                                                                 'kind': 'PRIMITIVE',
                                                                 'scale': 'RATIO',
                                                                 'unit': {'symbol': '%',
                                                                          'name': 'percent'},
                                                                 'range': {'lower': 0.0,
                                                                           'upper': 1.0,
                                                                           'discrete': False,
                                                                           'categories': None}},
                                                      'condition': {'threshold': {'operator': 'GEQ',
                                                                                  'value': 0.95},
                                                                    'range': None,
                                                                    'categorical': None,
                                                                    'statistical': None}},
 'dataset:loan_dataset#field-and-target-accuracy': {'name': 'Field and target accuracy',
                                                    'description': 'Validate source fidelity and '
                                                                   'plausible domains: Age 0–120, '
                                                                   'nonnegative '
                                                                   'income/expense/debt/loan '
                                                                   'amounts, positive loan term, '
                                                                   'Default_Risk in [0,1], and '
                                                                   'Loan_Approval_Status in {0,1}; '
                                                                   'reconcile labels against '
                                                                   'authoritative records.',
                                                    'metric': {'id': 'metric-data-accuracy',
                                                               'name': 'Data Accuracy / '
                                                                       'Correctness Rate',
                                                               'description': 'Fraction of data '
                                                                              'values that '
                                                                              'correctly represent '
                                                                              'the real-world '
                                                                              'entity they desc',
                                                               'kind': 'PRIMITIVE',
                                                               'scale': 'RATIO',
                                                               'unit': {'symbol': '%',
                                                                        'name': 'percent'},
                                                               'range': {'lower': 0.0,
                                                                         'upper': 1.0,
                                                                         'discrete': False,
                                                                         'categories': None}},
                                                    'condition': {'threshold': {'operator': 'GEQ',
                                                                                'value': 0.99},
                                                                  'range': None,
                                                                  'categorical': None,
                                                                  'statistical': None}},
 'dataset:loan_dataset#cross-field-consistency': {'name': 'Cross-field consistency',
                                                  'description': 'Ensure at least 99% of records '
                                                                 'satisfy documented domain and '
                                                                 'cross-field checks, including '
                                                                 'risk-score bounds, binary status '
                                                                 'values, nonnegative financial '
                                                                 'amounts, and consistency between '
                                                                 'application outcomes and source '
                                                                 'records; do not assume approval '
                                                                 'status is an in-scope model '
                                                                 'target.',
                                                  'metric': {'id': 'metric-data-consistency',
                                                             'name': 'Data Consistency Rate',
                                                             'description': 'Fraction of records '
                                                                            'that satisfy all '
                                                                            'defined cross-field '
                                                                            'and referential '
                                                                            'integri',
                                                             'kind': 'PRIMITIVE',
                                                             'scale': 'RATIO',
                                                             'unit': {'symbol': '%',
                                                                      'name': 'percent'},
                                                             'range': {'lower': 0.0,
                                                                       'upper': 1.0,
                                                                       'discrete': False,
                                                                       'categories': None}},
                                                  'condition': {'threshold': {'operator': 'GEQ',
                                                                              'value': 0.99},
                                                                'range': None,
                                                                'categorical': None,
                                                                'statistical': None}},
 'dataset:loan_dataset#categorical-target-balance': {'name': 'Categorical target balance',
                                                     'description': 'If Loan_Approval_Status is '
                                                                    'confirmed as a permitted '
                                                                    'historical '
                                                                    'training/evaluation label '
                                                                    '(rather than a target that '
                                                                    'automates approvals), '
                                                                    'maintain a '
                                                                    'minority-to-majority label '
                                                                    'ratio of at least 0.1 and '
                                                                    'report the class counts. For '
                                                                    'a continuous Default_Risk '
                                                                    'target, assess its '
                                                                    'distribution separately.',
                                                     'metric': {'id': 'metric-label-balance-ratio',
                                                                'name': 'Label Balance Ratio',
                                                                'description': 'Ratio of the '
                                                                               'minority class '
                                                                               'count to the '
                                                                               'majority class '
                                                                               'count in a '
                                                                               'classificatio',
                                                                'kind': 'PRIMITIVE',
                                                                'scale': 'RATIO',
                                                                'unit': {'symbol': 'ratio',
                                                                         'name': 'minority/majority '
                                                                                 'ratio'},
                                                                'range': {'lower': 0.0,
                                                                          'upper': 1.0,
                                                                          'discrete': False,
                                                                          'categories': None}},
                                                     'condition': {'threshold': {'operator': 'GEQ',
                                                                                 'value': 0.1},
                                                                   'range': None,
                                                                   'categorical': None,
                                                                   'statistical': None}},
 'dataset:loan_dataset#re-identification-risk-before-data-sharing': {'name': 'Re-identification '
                                                                             'risk before data '
                                                                             'sharing',
                                                                     'description': 'After '
                                                                                    'removing or '
                                                                                    'isolating '
                                                                                    'Applicant_ID '
                                                                                    'and '
                                                                                    'generalizing '
                                                                                    'relevant '
                                                                                    'quasi-identifiers '
                                                                                    '(such as age '
                                                                                    'and '
                                                                                    'City/Town), '
                                                                                    'require '
                                                                                    'k-anonymity '
                                                                                    'of at least 5 '
                                                                                    'before '
                                                                                    'external '
                                                                                    'disclosure or '
                                                                                    'other '
                                                                                    'release; '
                                                                                    'apply '
                                                                                    'stricter '
                                                                                    'access '
                                                                                    'controls to '
                                                                                    'the '
                                                                                    'identifiable '
                                                                                    'training '
                                                                                    'table.',
                                                                     'metric': {'id': 'metric-k-anonymity',
                                                                                'name': 'k-Anonymity',
                                                                                'description': 'Minimum '
                                                                                               'number '
                                                                                               'of '
                                                                                               'records '
                                                                                               'that '
                                                                                               'share '
                                                                                               'the '
                                                                                               'same '
                                                                                               'quasi-identifier '
                                                                                               'combination. '
                                                                                               'k '
                                                                                               '= ',
                                                                                'kind': 'PRIMITIVE',
                                                                                'scale': 'ORDINAL',
                                                                                'unit': {'symbol': 'k',
                                                                                         'name': 'equivalence '
                                                                                                 'class '
                                                                                                 'size'},
                                                                                'range': {'lower': 1.0,
                                                                                          'upper': None,
                                                                                          'discrete': True,
                                                                                          'categories': None}},
                                                                     'condition': {'threshold': {'operator': 'GEQ',
                                                                                                 'value': 5.0},
                                                                                   'range': None,
                                                                                   'categorical': None,
                                                                                   'statistical': None}}}
EVALUATORS = [
    ('dataset:loan_dataset#required-field-completeness', evaluate_loan_completeness),
    ('dataset:loan_dataset#field-and-target-accuracy', evaluate_loan_accuracy),
    ('dataset:loan_dataset#cross-field-consistency', evaluate_loan_consistency),
    ('dataset:loan_dataset#categorical-target-balance', evaluate_loan_label_balance),
    ('dataset:loan_dataset#re-identification-risk-before-data-sharing', evaluate_loan_k_anonymity),
]
REPORT_NAMES = {'EVALUATION': 'loan-data-evaluation', 'TEST': 'loan-data-test'}

OPERATORS = {"GEQ": operator.ge, "LEQ": operator.le, "GT": operator.gt,
             "LT": operator.lt, "EQ": operator.eq, "NEQ": operator.ne}


def _passed(value: Any, condition: dict[str, Any]) -> bool | None:
    """Return whether the value satisfies the condition, or None when it cannot be decided."""
    kind, body = next(iter(condition.items()))
    if kind == "composite":
        outcomes = [_passed(value, child) for child in body["conditions"]]
        decisive = body["operator"] == "OR"
        if decisive in outcomes:
            return decisive
        return None if None in outcomes else not decisive
    if kind == "categorical":
        return value in body["allowed"] if isinstance(value, str) else None
    if kind not in ("threshold", "range") or isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    if kind == "threshold":
        return OPERATORS[body["operator"]](value, body["value"])
    if body["inclusive"]:
        return body["lower"] <= value <= body["upper"]
    return body["lower"] < value < body["upper"]


def _measure(evaluate: Any, entity: Any, kwargs: dict[str, Any]) -> dict[str, Any]:
    parameters = inspect.signature(evaluate).parameters
    if not any(item.kind is inspect.Parameter.VAR_KEYWORD for item in parameters.values()):
        kwargs = {key: value for key, value in kwargs.items() if key in parameters}
    try:
        return evaluate(entity, **kwargs)
    except Exception as exc:
        return {"status": "ERROR", "error": f"{type(exc).__name__}: {exc}"}


def build_reports(measurements: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Build the EVALUATION/TEST reports from the measurement of each objective."""
    metrics: dict[str, Any] = {}
    checks, verdicts, issues = [], [], []
    for reference, measurement in measurements.items():
        condition = OBJECTIVES[reference]["condition"]
        result = measurement.get("metric_result")
        status = measurement.get("status", "SUCCESS")
        if status != "SUCCESS" or not result:
            verdicts.append("ERROR" if status == "ERROR" else "INCONCLUSIVE")
            issues.append(f"{reference}: {measurement.get('error') or 'no measurement'}")
            continue
        metrics.setdefault(result["metric_id"], result)
        passed = _passed(result["value"], condition)
        if passed is None:
            verdicts.append("INCONCLUSIVE")
            issues.append(f"{reference}: the condition cannot be decided for the measured value")
            continue
        verdicts.append("PASS" if passed else "FAIL")
        checks.append({"measured": json.dumps(result["value"], sort_keys=True, default=str),
                       "expected": condition, "passed": passed})
    reports = {}
    if "EVALUATION" in REPORT_NAMES and metrics:
        reports["EVALUATION"] = {"kind": "EVALUATION", "objectives": list(measurements),
                                 "content": {"evaluation": {"metrics": list(metrics.values())}}}
    if "TEST" in REPORT_NAMES:
        verdict = next(item for item in ("ERROR", "FAIL", "INCONCLUSIVE", "PASS") if item in verdicts)
        reports["TEST"] = {"kind": "TEST", "objectives": list(measurements), "content": {"test": {
            "results": checks, "verdict": verdict,
            "summary": "; ".join(issues) or "All objective checks are determinate."}}}
    return reports


def publish(entity: Any, reports: dict[str, dict[str, Any]]) -> None:
    """Save the reports as named extensions on the entity, replacing existing ones."""
    names = {REPORT_NAMES[kind] for kind in reports}
    kept = [ext for ext in entity.extensions or []
            if not (ext.get("kind") == "compliance-report" and ext.get("name") in names)]
    entity.extensions = kept + [{"kind": "compliance-report", "name": REPORT_NAMES[kind], "spec": {'name': REPORT_NAMES[kind], **report}}
                                for kind, report in reports.items()]
                                
    entity.save(update=True)


def run(project, entity: Any, **kwargs: Any) -> dict[str, dict[str, Any]]:
    """Evaluate every objective on the entity, then save the resulting reports on it."""
    measurements = {reference: _measure(evaluate, entity, kwargs) for reference, evaluate in EVALUATORS}
    errors = {
        reference: measurement.get("error", "evaluator returned an ERROR result")
        for reference, measurement in measurements.items()
        if measurement.get("status") == "ERROR"
    }
    if errors:
        raise RuntimeError(f"Evaluation aborted because one or more evaluators failed: {errors}")
    reports = build_reports(measurements)
    publish(entity, reports)
    return reports
