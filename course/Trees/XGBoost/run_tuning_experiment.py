"""Synthetic longitudinal classification experiment.

The data is generated from a latent disease-severity process and noisy repeated
measurements. It is educational synthetic data, not clinical evidence.
"""

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import sklearn
import xgboost
from matplotlib.lines import Line2D
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, balanced_accuracy_score, recall_score, roc_auc_score
from xgboost import XGBClassifier

SEED = 20261113
OUT_DIR = Path(__file__).parent
VISUALS_DIR = OUT_DIR / "visuals"


def make_data():
    rng = np.random.default_rng(SEED)
    n_patients = 1200
    patient_id = np.arange(n_patients)
    baseline_date = pd.date_range("2021-01-01", periods=n_patients, freq="D")
    age = rng.normal(68, 7, n_patients).clip(48, 88)
    latent_burden = rng.beta(2.2, 4.5, n_patients)
    baseline_motor_latent = 94 - 43 * latent_burden - 0.13 * (age - 68) + rng.normal(0, 2.5, n_patients)
    baseline_cognitive_latent = 96 - 32 * latent_burden - 0.08 * (age - 68) + rng.normal(0, 2.2, n_patients)
    motor_slope_latent = -(0.8 + 3.0 * latent_burden + 0.025 * (age - 68) + rng.normal(0, 0.65, n_patients))
    cognitive_slope_latent = -(0.6 + 1.8 * latent_burden + rng.normal(0, 0.55, n_patients))
    tremor_slope_latent = 0.08 + 0.7 * latent_burden + rng.normal(0, 0.12, n_patients)

    measurement_rows = []
    for patient in patient_id:
        for month in (0, 6, 12):
            measurement_rows.append(
                {
                    "patient_id": patient,
                    "month": month,
                    "motor_score": baseline_motor_latent[patient] + motor_slope_latent[patient] * month / 12 + rng.normal(0, 2.0),
                    "cognitive_score": baseline_cognitive_latent[patient] + cognitive_slope_latent[patient] * month / 12 + rng.normal(0, 1.7),
                    "tremor_score": 1.4 + tremor_slope_latent[patient] * month / 12 + rng.normal(0, 0.12),
                }
            )
    longitudinal = pd.DataFrame(measurement_rows)
    baseline = longitudinal[longitudinal.month == 0].set_index("patient_id")
    followup = longitudinal[longitudinal.month == 12].set_index("patient_id")
    motor_decline = followup.motor_score - baseline.motor_score
    cognitive_decline = followup.cognitive_score - baseline.cognitive_score
    tremor_change = followup.tremor_score - baseline.tremor_score

    # The future outcome is generated from latent deterioration after month 12,
    # not from a hand-created feature in the training table.
    future_motor = baseline_motor_latent + 2 * motor_slope_latent + rng.normal(0, 3.2, n_patients)
    future_cognitive = baseline_cognitive_latent + 2 * cognitive_slope_latent + rng.normal(0, 2.7, n_patients)
    progression = ((future_motor < 68) | (future_cognitive < 67)).astype(int)

    X = pd.DataFrame(
        {
            "age": age,
            "baseline_motor_score": baseline.motor_score.to_numpy(),
            "baseline_cognitive_score": baseline.cognitive_score.to_numpy(),
            "motor_decline_per_year": motor_decline.to_numpy(),
            "cognitive_decline_per_year": cognitive_decline.to_numpy(),
            "tremor_change_per_year": tremor_change.to_numpy(),
        }
    )
    # Defined only for evaluation and plotting after the features/outcome exist.
    rare_pattern = ((X.baseline_motor_score < 68) & (X.motor_decline_per_year < -3.2)).astype(int).to_numpy()
    frame = X.assign(patient_id=patient_id, baseline_date=baseline_date, progression_within_12m=progression, rare_pattern=rare_pattern)
    return X, frame, longitudinal


def score(y, probability, rare_mask, threshold=0.5):
    prediction = (probability >= threshold).astype(int)
    return {
        "accuracy": accuracy_score(y, prediction),
        "balanced_accuracy": balanced_accuracy_score(y, prediction),
        "roc_auc": roc_auc_score(y, probability),
        "overall_recall": recall_score(y, prediction, zero_division=0),
        "rare_pattern_recall": recall_score(y[rare_mask], prediction[rare_mask], zero_division=0),
        "rare_rows": int(rare_mask.sum()),
    }


def add_interaction(X):
    enhanced = X.copy()
    enhanced["low_baseline_x_motor_decline"] = np.maximum(0, 68 - enhanced.baseline_motor_score) * np.maximum(0, -enhanced.motor_decline_per_year)
    return enhanced


def generate_visuals(frame, test_slice, probabilities, results, longitudinal):
    VISUALS_DIR.mkdir(exist_ok=True)
    test_frame = frame.iloc[test_slice]
    rare_ids = test_frame.loc[test_frame.rare_pattern == 1, "patient_id"].to_numpy()
    ordinary_ids = test_frame.loc[test_frame.rare_pattern == 0, "patient_id"].to_numpy()
    selected = np.concatenate([ordinary_ids[:5], rare_ids[:5]])
    trajectories = longitudinal[longitudinal.patient_id.isin(selected)]
    rare_set = set(rare_ids)
    fig, ax = plt.subplots(figsize=(11, 5.2))
    for patient_id, patient in trajectories.groupby("patient_id"):
        rare = patient_id in rare_set
        ax.plot(patient.month, patient.motor_score, marker="o", linewidth=2.2 if rare else 1.2, alpha=0.9 if rare else 0.45, color="#dc2626" if rare else "#64748b")
    ax.set_title("Repeated measurements reveal different trajectories", fontweight="bold")
    ax.set_xlabel("Months from baseline")
    ax.set_ylabel("Motor score")
    ax.legend(
        handles=[
            Line2D([0], [0], color="#dc2626", linewidth=2.2, label="Post hoc rare-pattern subgroup"),
            Line2D([0], [0], color="#64748b", linewidth=1.2, label="Other trajectories"),
        ],
        frameon=False,
        loc="lower left",
    )
    ax.text(0.02, 0.16, "Colour shows a feature-defined subgroup, not the prediction outcome.", transform=ax.transAxes, fontsize=10)
    ax.grid(alpha=0.2)
    fig.tight_layout()
    fig.savefig(VISUALS_DIR / "longitudinal_trajectory_features.png", dpi=180, bbox_inches="tight", facecolor="white")
    plt.close(fig)

    rare = test_frame.rare_pattern.to_numpy() == 1
    fig, ax = plt.subplots(figsize=(9, 5.2))
    baseline_motor = test_frame.baseline_motor_score.to_numpy()
    motor_decline = test_frame.motor_decline_per_year.to_numpy()
    ax.scatter(baseline_motor[~rare], motor_decline[~rare], color="#64748b", alpha=0.55, s=34, label="Other trajectories")
    ax.scatter(baseline_motor[rare], motor_decline[rare], color="#dc2626", edgecolor="white", linewidth=0.7, s=70, label="Rare trajectory subgroup")
    ax.axvline(68, color="#dc2626", linestyle="--", linewidth=1, alpha=0.65)
    ax.axhline(-3.2, color="#dc2626", linestyle="--", linewidth=1, alpha=0.65)
    ax.set_xlabel("Baseline motor score")
    ax.set_ylabel("Motor decline per year")
    ax.set_title("The rare trajectory pattern in feature space", fontweight="bold")
    ax.legend(frameon=False)
    ax.grid(alpha=0.2)
    fig.tight_layout()
    fig.savefig(VISUALS_DIR / "trajectory_interaction_scatter.png", dpi=180, bbox_inches="tight", facecolor="white")
    plt.close(fig)

    labels = ["Constrained\nXGBoost", "Recall-tuned\nXGBoost", "Logistic\n+ interaction"]
    fig, axes = plt.subplots(1, 3, figsize=(13, 4.8), constrained_layout=True)
    for ax, (column, title) in zip(axes, [("accuracy", "Accuracy"), ("balanced_accuracy", "Balanced accuracy"), ("roc_auc", "ROC AUC")]):
        values = results[column].to_numpy()
        bars = ax.bar(labels, values, color=["#94a3b8", "#f59e0b", "#2563eb"])
        ax.set_title(title, fontweight="bold")
        ax.set_ylim(0, 1)
        ax.grid(axis="y", alpha=0.2)
        for bar, value in zip(bars, values):
            ax.text(bar.get_x() + bar.get_width() / 2, value + 0.03, f"{value:.3f}", ha="center", fontsize=9)
    fig.suptitle("One headline metric does not tell the progression-risk story", fontsize=15, fontweight="bold")
    fig.savefig(VISUALS_DIR / "classification_metric_comparison.png", dpi=180, bbox_inches="tight", facecolor="white")
    plt.close(fig)

    rare_mask = test_frame.rare_pattern.to_numpy() == 1
    y_test = test_frame.progression_within_12m.to_numpy()
    recall_values = [recall_score(y_test[rare_mask], (probabilities[approach] >= 0.5).astype(int)[rare_mask], zero_division=0) for approach in results.approach]
    fig, ax = plt.subplots(figsize=(9, 4.8))
    bars = ax.bar([label.replace("\n", " ") for label in labels], recall_values, color=["#94a3b8", "#f59e0b", "#2563eb"])
    for bar, value in zip(bars, recall_values):
        ax.text(bar.get_x() + bar.get_width() / 2, value + 0.03, f"{value:.0%}", ha="center", fontsize=11)
    ax.set_ylim(0, 1.15)
    ax.set_ylabel("Recall at threshold 0.5")
    ax.set_title("Recall on the post hoc rare trajectory subgroup", fontweight="bold")
    ax.grid(axis="y", alpha=0.2)
    fig.tight_layout()
    fig.savefig(VISUALS_DIR / "classification_rare_pattern_recall.png", dpi=180, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def main():
    X, frame, longitudinal = make_data()
    X_interaction = add_interaction(X)
    n = len(frame)
    train_end, validation_end = int(0.60 * n), int(0.80 * n)
    train, validation, test = slice(0, train_end), slice(train_end, validation_end), slice(validation_end, n)
    candidates = [
        {"name": "shallow_regularised", "max_depth": 2, "min_child_weight": 50, "subsample": 0.8, "colsample_bytree": 0.8, "reg_lambda": 20.0},
        {"name": "balanced", "max_depth": 3, "min_child_weight": 20, "subsample": 0.9, "colsample_bytree": 0.9, "reg_lambda": 8.0},
        {"name": "interaction_aware", "max_depth": 4, "min_child_weight": 1, "subsample": 0.9, "colsample_bytree": 1.0, "reg_lambda": 2.0},
    ]
    validation_rows = []
    fitted = {}
    for candidate in candidates:
        model = XGBClassifier(n_estimators=250, learning_rate=0.04, objective="binary:logistic", eval_metric="logloss", random_state=SEED, n_jobs=1, tree_method="hist", **{key: value for key, value in candidate.items() if key != "name"})
        candidate_X = X_interaction if candidate["name"] == "interaction_aware" else X
        model.fit(candidate_X.iloc[train], frame.progression_within_12m.iloc[train])
        probability = model.predict_proba(candidate_X.iloc[validation])[:, 1]
        rare = frame.rare_pattern.iloc[validation].to_numpy() == 1
        metrics = score(frame.progression_within_12m.iloc[validation].to_numpy(), probability, rare)
        metrics["expert_selection_score"] = 0.80 * (1 - metrics["rare_pattern_recall"]) + 0.20 * (1 - metrics["roc_auc"])
        metrics["candidate"] = candidate["name"]
        validation_rows.append(metrics)
        fitted[candidate["name"]] = candidate
    validation_results = pd.DataFrame(validation_rows)
    agent_search = validation_results[validation_results.candidate.isin(["shallow_regularised", "balanced"])]
    agent_choice = agent_search.loc[agent_search.accuracy.idxmax(), "candidate"]
    expert_choice = validation_results.loc[validation_results.expert_selection_score.idxmin(), "candidate"]

    test_rows, probabilities = [], {}
    for approach, choice in (("Constrained XGBoost: aggregate accuracy", agent_choice), ("XGBoost: rare-pattern recall", expert_choice)):
        candidate = fitted[choice]
        candidate_X = X_interaction if choice == "interaction_aware" else X
        model = XGBClassifier(n_estimators=250, learning_rate=0.04, objective="binary:logistic", eval_metric="logloss", random_state=SEED, n_jobs=1, tree_method="hist", **{key: value for key, value in candidate.items() if key != "name"})
        model.fit(candidate_X.iloc[:validation_end], frame.progression_within_12m.iloc[:validation_end])
        probability = model.predict_proba(candidate_X.iloc[test])[:, 1]
        rare = frame.rare_pattern.iloc[test].to_numpy() == 1
        metrics = score(frame.progression_within_12m.iloc[test].to_numpy(), probability, rare)
        metrics.update({"approach": approach, "selected_candidate": choice})
        test_rows.append(metrics)
        probabilities[approach] = probability
    test_results = pd.DataFrame(test_rows)

    simple_model = LogisticRegression(C=1.0, max_iter=2000, random_state=SEED)
    simple_model.fit(X_interaction.iloc[:validation_end], frame.progression_within_12m.iloc[:validation_end])
    simple_probability = simple_model.predict_proba(X_interaction.iloc[test])[:, 1]
    rare = frame.rare_pattern.iloc[test].to_numpy() == 1
    simple_metrics = score(frame.progression_within_12m.iloc[test].to_numpy(), simple_probability, rare)
    simple_results = pd.DataFrame([{"approach": "Logistic regression + explicit trajectory interaction", "selected_candidate": "LogisticRegression(C=1.0)", **simple_metrics}])
    probabilities["Logistic regression + explicit trajectory interaction"] = simple_probability

    validation_results.to_csv(OUT_DIR / "validation_tuning_results.csv", index=False)
    test_results.to_csv(OUT_DIR / "test_tuning_results.csv", index=False)
    simple_results.to_csv(OUT_DIR / "simple_model_results.csv", index=False)
    frame.to_csv(OUT_DIR / "synthetic_patient_features.csv", index=False)
    longitudinal.to_csv(OUT_DIR / "synthetic_longitudinal_measurements.csv", index=False)
    combined = pd.concat([test_results, simple_results], ignore_index=True)
    generate_visuals(frame, test, probabilities, combined, longitudinal)
    print(f"xgboost={xgboost.__version__}; scikit-learn={sklearn.__version__}; seed={SEED}")
    print("\nValidation search")
    print(validation_results.round(3).to_string(index=False))
    print("\nUntouched chronological patient-cohort test")
    print(test_results.round(3).to_string(index=False))
    print("\nSimple benchmark")
    print(simple_results.round(3).to_string(index=False))


if __name__ == "__main__":
    main()
