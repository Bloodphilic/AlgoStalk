"""Controlled XGBoost classification experiment for the LinkedIn article.

All data is synthetic. The experiment compares a constrained XGBoost classifier
with a logistic model after an explicitly known interaction is encoded.
"""

from pathlib import Path

import numpy as np
import pandas as pd
import sklearn
import xgboost
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, balanced_accuracy_score, recall_score, roc_auc_score
from xgboost import XGBClassifier

SEED = 20261030
OUT_DIR = Path(__file__).parent
FEATURES = ["day_index", "dow_sin", "dow_cos", "year_sin", "year_cos", "campaign", "campaign_budget", "weekend_launch"]


def make_data():
    rng = np.random.default_rng(SEED)
    date = pd.date_range("2024-01-01", periods=730, freq="D")
    day = np.arange(len(date))
    weekday = date.dayofweek.to_numpy()
    weekend = weekday >= 5
    campaign = ((day % 29 == 4) | (day % 29 == 5)).astype(int)
    campaign_budget = campaign * np.where(day % 58 == 4, 180.0, 90.0)
    weekend_launch = (campaign.astype(bool) & weekend).astype(int)
    # A binary operational outcome: did the day's demand cross the capacity
    # threshold? The rare known interaction has a much higher probability.
    logit = (
        -1.45
        + 0.35 * np.sin(2 * np.pi * weekday / 7)
        + 0.25 * np.sin(2 * np.pi * day / 365.25)
        + 0.65 * campaign
        + 0.004 * campaign_budget
        + 3.15 * weekend_launch
    )
    probability = 1 / (1 + np.exp(-logit))
    outcome = rng.binomial(1, probability)
    X = pd.DataFrame(
        {
            "day_index": day,
            "dow_sin": np.sin(2 * np.pi * weekday / 7),
            "dow_cos": np.cos(2 * np.pi * weekday / 7),
            "year_sin": np.sin(2 * np.pi * day / 365.25),
            "year_cos": np.cos(2 * np.pi * day / 365.25),
            "campaign": campaign,
            "campaign_budget": campaign_budget,
            "weekend_launch": weekend_launch,
        }
    )
    scenario = np.where(weekend_launch == 1, "rare_weekend_launch", np.where(campaign == 1, "ordinary_campaign", "ordinary_day"))
    frame = X.assign(date=date, outcome=outcome, scenario=scenario)
    return X, frame


def score(y, probability, scenario, threshold=0.5):
    prediction = (probability >= threshold).astype(int)
    ordinary = scenario == "ordinary_day"
    rare = scenario == "rare_weekend_launch"
    return {
        "accuracy": accuracy_score(y, prediction),
        "balanced_accuracy": balanced_accuracy_score(y, prediction),
        "roc_auc": roc_auc_score(y, probability),
        "ordinary_recall": recall_score(y[ordinary], prediction[ordinary], zero_division=0),
        "rare_launch_recall": recall_score(y[rare], prediction[rare], zero_division=0),
        "rare_rows": int(rare.sum()),
    }


def main():
    X, frame = make_data()
    n = len(frame)
    train_end, validation_end = int(0.60 * n), int(0.80 * n)
    train = slice(0, train_end)
    validation = slice(train_end, validation_end)
    test = slice(validation_end, n)
    candidates = [
        {"name": "shallow_regularised", "max_depth": 2, "min_child_weight": 12, "subsample": 0.8, "colsample_bytree": 0.8, "reg_lambda": 12.0},
        {"name": "balanced", "max_depth": 3, "min_child_weight": 4, "subsample": 0.9, "colsample_bytree": 0.9, "reg_lambda": 4.0},
        {"name": "interaction_aware", "max_depth": 4, "min_child_weight": 1, "subsample": 0.9, "colsample_bytree": 1.0, "reg_lambda": 2.0},
    ]
    validation_rows = []
    fitted = {}
    for candidate in candidates:
        model = XGBClassifier(
            n_estimators=250,
            learning_rate=0.04,
            objective="binary:logistic",
            eval_metric="logloss",
            random_state=SEED,
            n_jobs=1,
            tree_method="hist",
            **{key: value for key, value in candidate.items() if key != "name"},
        )
        model.fit(X.iloc[train], frame.outcome.iloc[train])
        probability = model.predict_proba(X.iloc[validation])[:, 1]
        metrics = score(frame.outcome.iloc[validation].to_numpy(), probability, frame.scenario.iloc[validation].to_numpy())
        metrics["expert_selection_score"] = 0.35 * (1 - metrics["ordinary_recall"]) + 0.65 * (1 - metrics["rare_launch_recall"])
        metrics["candidate"] = candidate["name"]
        validation_rows.append(metrics)
        fitted[candidate["name"]] = candidate
    validation_results = pd.DataFrame(validation_rows)
    # The initial search optimises aggregate accuracy. The expert selection
    # gives the rare known launch a materially higher cost.
    agent_choice = validation_results.loc[validation_results.accuracy.idxmax(), "candidate"]
    expert_choice = validation_results.loc[validation_results.expert_selection_score.idxmin(), "candidate"]

    test_rows = []
    for approach, choice in (("Constrained XGBoost: aggregate accuracy", agent_choice), ("Interaction-aware XGBoost: weighted recall", expert_choice)):
        candidate = fitted[choice]
        model = XGBClassifier(
            n_estimators=250,
            learning_rate=0.04,
            objective="binary:logistic",
            eval_metric="logloss",
            random_state=SEED,
            n_jobs=1,
            tree_method="hist",
            **{key: value for key, value in candidate.items() if key != "name"},
        )
        model.fit(X.iloc[:validation_end], frame.outcome.iloc[:validation_end])
        metrics = score(frame.outcome.iloc[test].to_numpy(), model.predict_proba(X.iloc[test])[:, 1], frame.scenario.iloc[test].to_numpy())
        metrics.update({"approach": approach, "selected_candidate": choice})
        test_rows.append(metrics)
    test_results = pd.DataFrame(test_rows)

    # Once the known campaign/weekend interaction is explicit, logistic
    # regression is a transparent and much cheaper benchmark.
    simple_model = LogisticRegression(C=1.0, max_iter=2000, random_state=SEED)
    simple_model.fit(X.iloc[:validation_end], frame.outcome.iloc[:validation_end])
    simple_metrics = score(frame.outcome.iloc[test].to_numpy(), simple_model.predict_proba(X.iloc[test])[:, 1], frame.scenario.iloc[test].to_numpy())
    simple_results = pd.DataFrame([{"approach": "Logistic regression + explicit interaction", "selected_candidate": "LogisticRegression(C=1.0)", **simple_metrics}])

    validation_results.to_csv(OUT_DIR / "validation_tuning_results.csv", index=False)
    test_results.to_csv(OUT_DIR / "test_tuning_results.csv", index=False)
    simple_results.to_csv(OUT_DIR / "simple_model_results.csv", index=False)
    print(f"xgboost={xgboost.__version__}; scikit-learn={sklearn.__version__}; seed={SEED}")
    print("\nValidation search")
    print(validation_results.round(3).to_string(index=False))
    print("\nUntouched chronological test")
    print(test_results.round(3).to_string(index=False))
    print("\nSimple benchmark")
    print(simple_results.round(3).to_string(index=False))


if __name__ == "__main__":
    main()
