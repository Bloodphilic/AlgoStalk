"""Simple, reproducible LightGBM/XGBoost churn comparison.

Dataset: IBM Telco Customer Churn sample.
The raw data is downloaded at runtime from IBM's public repository.
"""

from pathlib import Path
from time import perf_counter
from urllib.request import urlopen

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import lightgbm as lgb
import xgboost as xgb
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, confusion_matrix, precision_recall_curve, precision_score, recall_score, roc_auc_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

SEED = 20261113
ROOT = Path(__file__).parent
DATA_DIR = ROOT / "data"
VISUALS_DIR = ROOT / "visuals"
URL = "https://raw.githubusercontent.com/IBM/telco-customer-churn-on-icp4d/master/data/Telco-Customer-Churn.csv"


def load_data():
    DATA_DIR.mkdir(exist_ok=True)
    path = DATA_DIR / "Telco-Customer-Churn.csv"
    if not path.exists():
        path.write_bytes(urlopen(URL, timeout=30).read())
    data = pd.read_csv(path)
    data["TotalCharges"] = pd.to_numeric(data["TotalCharges"], errors="coerce")
    data["Churn"] = (data["Churn"] == "Yes").astype(int)
    return data


def choose_threshold(y, probability, minimum_precision=0.60):
    precision, recall, thresholds = precision_recall_curve(y, probability)
    valid = np.where(precision[:-1] >= minimum_precision)[0]
    if len(valid) == 0:
        return 0.5
    best = valid[np.argmax(recall[:-1][valid])]
    return float(thresholds[best])


def evaluate(name, model, X_train, y_train, X_valid, y_valid, X_test, y_test):
    start = perf_counter()
    model.fit(X_train, y_train)
    train_seconds = perf_counter() - start
    valid_probability = model.predict_proba(X_valid)[:, 1]
    threshold = choose_threshold(y_valid, valid_probability)
    test_probability = model.predict_proba(X_test)[:, 1]
    prediction = (test_probability >= threshold).astype(int)
    return {
        "model": name,
        "train_seconds": train_seconds,
        "threshold": threshold,
        "pr_auc": average_precision_score(y_test, test_probability),
        "roc_auc": roc_auc_score(y_test, test_probability),
        "precision_at_threshold": precision_score(y_test, prediction, zero_division=0),
        "recall_at_threshold": recall_score(y_test, prediction, zero_division=0),
        "tn": confusion_matrix(y_test, prediction).ravel()[0],
        "fp": confusion_matrix(y_test, prediction).ravel()[1],
        "fn": confusion_matrix(y_test, prediction).ravel()[2],
        "tp": confusion_matrix(y_test, prediction).ravel()[3],
    }, test_probability


def main():
    data = load_data()
    X = data.drop(columns=["Churn", "customerID"])
    y = data["Churn"]
    X_train, X_temp, y_train, y_temp = train_test_split(X, y, test_size=0.40, stratify=y, random_state=SEED)
    X_valid, X_test, y_valid, y_test = train_test_split(X_temp, y_temp, test_size=0.50, stratify=y_temp, random_state=SEED)
    numeric = X_train.select_dtypes(include=np.number).columns.tolist()
    categorical = X_train.select_dtypes(exclude=np.number).columns.tolist()
    preprocessor = ColumnTransformer([
        ("numeric", Pipeline([("impute", SimpleImputer(strategy="median")), ("scale", StandardScaler())]), numeric),
        ("categorical", Pipeline([("impute", SimpleImputer(strategy="most_frequent")), ("onehot", OneHotEncoder(handle_unknown="ignore"))]), categorical),
    ])
    X_train_p = preprocessor.fit_transform(X_train)
    X_valid_p = preprocessor.transform(X_valid)
    X_test_p = preprocessor.transform(X_test)
    models = {
        "Logistic regression": LogisticRegression(max_iter=2000, class_weight="balanced", random_state=SEED),
        "LightGBM": lgb.LGBMClassifier(n_estimators=250, learning_rate=0.04, num_leaves=24, max_depth=6, subsample=0.85, colsample_bytree=0.85, class_weight="balanced", random_state=SEED, verbosity=-1),
        "XGBoost": xgb.XGBClassifier(n_estimators=250, learning_rate=0.04, max_depth=4, min_child_weight=4, subsample=0.85, colsample_bytree=0.85, objective="binary:logistic", eval_metric="logloss", tree_method="hist", n_jobs=1, random_state=SEED),
    }
    results, probabilities = [], {}
    for name, model in models.items():
        metrics, probability = evaluate(name, model, X_train_p, y_train, X_valid_p, y_valid, X_test_p, y_test)
        results.append(metrics)
        probabilities[name] = probability
    results = pd.DataFrame(results)
    results.to_csv(ROOT / "results.csv", index=False)
    pd.DataFrame({"actual": y_test.to_numpy(), **probabilities}).to_csv(ROOT / "test_predictions.csv", index=False)
    VISUALS_DIR.mkdir(exist_ok=True)

    fig, axes = plt.subplots(1, 3, figsize=(13, 4.8), constrained_layout=True)
    for ax, metric, title in zip(axes, ["pr_auc", "roc_auc", "recall_at_threshold"], ["PR-AUC", "ROC-AUC", "Recall at precision >= 0.60"]):
        bars = ax.bar(results.model, results[metric], color=["#64748b", "#16a34a", "#2563eb"])
        ax.set_title(title, fontweight="bold")
        ax.set_ylim(0, 1)
        ax.tick_params(axis="x", rotation=25)
        ax.grid(axis="y", alpha=0.2)
        for bar, value in zip(bars, results[metric]):
            ax.text(bar.get_x() + bar.get_width() / 2, value + 0.025, f"{value:.3f}", ha="center", fontsize=9)
    fig.suptitle("Churn model comparison on the untouched test set", fontsize=15, fontweight="bold")
    fig.savefig(VISUALS_DIR / "model_comparison.png", dpi=180, bbox_inches="tight", facecolor="white")
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(8, 4.8))
    bars = ax.bar(results.model, results.train_seconds, color=["#64748b", "#16a34a", "#2563eb"])
    ax.set_title("Training time is part of the model trade-off", fontweight="bold")
    ax.set_ylabel("Seconds")
    ax.tick_params(axis="x", rotation=25)
    ax.grid(axis="y", alpha=0.2)
    for bar, value in zip(bars, results.train_seconds):
        ax.text(bar.get_x() + bar.get_width() / 2, value + max(results.train_seconds) * 0.03, f"{value:.3f}", ha="center", fontsize=9)
    fig.tight_layout()
    fig.savefig(VISUALS_DIR / "training_time.png", dpi=180, bbox_inches="tight", facecolor="white")
    plt.close(fig)

    fig, axes = plt.subplots(1, 3, figsize=(12, 3.8), constrained_layout=True)
    for ax, (_, row) in zip(axes, results.iterrows()):
        prediction = (probabilities[row.model] >= row.threshold).astype(int)
        matrix = confusion_matrix(y_test, prediction)
        image = ax.imshow(matrix, cmap="Blues")
        ax.set_title(row.model, fontweight="bold")
        ax.set_xlabel("Predicted")
        ax.set_ylabel("Actual")
        ax.set_xticks([0, 1], ["Stay", "Churn"])
        ax.set_yticks([0, 1], ["Stay", "Churn"])
        for i in range(2):
            for j in range(2):
                ax.text(j, i, matrix[i, j], ha="center", va="center", color="white" if matrix[i, j] > matrix.max() * 0.55 else "black")
    fig.suptitle("Confusion matrices at each model's selected threshold", fontsize=14, fontweight="bold")
    fig.savefig(VISUALS_DIR / "confusion_matrices.png", dpi=180, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"Rows={len(data)}; churn_rate={y.mean():.3f}; seed={SEED}")
    print(results.round(4).to_string(index=False))


if __name__ == "__main__":
    main()
