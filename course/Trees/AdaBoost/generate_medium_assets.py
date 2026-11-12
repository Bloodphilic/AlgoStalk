"""Generate the data exports and charts used by the Medium case study.

All exports are derived from the deterministic synthetic experiment. They are
not production website data.
"""

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.ensemble import AdaBoostRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error
from sklearn.tree import DecisionTreeRegressor

from generate_visuals import LEARNING_RATE, SEED, make_data


ROOT = Path(__file__).parent
VISUALS_DIR = ROOT / "visuals"
DATA_DIR = ROOT / "medium_data"
VISUALS_DIR.mkdir(exist_ok=True)
DATA_DIR.mkdir(exist_ok=True)


def fit_and_score(X, frame):
    n_rows = len(frame)
    train_end, validation_end = int(0.60 * n_rows), int(0.80 * n_rows)
    split_labels = np.full(n_rows, "test", dtype=object)
    split_labels[:train_end] = "train"
    split_labels[train_end:validation_end] = "validation"
    export = frame.copy()
    export["split"] = split_labels
    export = export.join(X)

    rows = []
    predictions = {}
    for loss in ("linear", "square", "exponential"):
        model = AdaBoostRegressor(
            estimator=DecisionTreeRegressor(max_depth=3, random_state=SEED),
            n_estimators=20,
            learning_rate=LEARNING_RATE,
            loss=loss,
            random_state=SEED,
        ).fit(X.iloc[:train_end], frame.traffic.iloc[:train_end])
        prediction = model.predict(X)
        export[f"prediction_{loss}"] = prediction
        predictions[loss] = prediction

        for split_name, split in (("validation", slice(train_end, validation_end)), ("test", slice(validation_end, n_rows))):
            segments = {
                "ordinary": ~X.marketing_event.iloc[split].to_numpy().astype(bool) & ~frame.attack_like.iloc[split].to_numpy(),
                "rare_known_campaign": frame.rare_campaign.iloc[split].to_numpy(),
                "simulated_attack_like": frame.attack_like.iloc[split].to_numpy(),
            }
            for segment, mask in segments.items():
                if mask.any():
                    actual = frame.traffic.iloc[split].to_numpy()[mask]
                    predicted = prediction[split][mask]
                    rows.append(
                        {
                            "split": split_name,
                            "loss": loss,
                            "segment": segment,
                            "mae": mean_absolute_error(actual, predicted),
                            "rmse": np.sqrt(mean_squared_error(actual, predicted)),
                            "n": int(mask.sum()),
                        }
                    )
    return export, pd.DataFrame(rows)


def first_round_audit(X, frame):
    train_end = int(0.60 * len(frame))
    y_train = frame.traffic.iloc[:train_end].to_numpy()
    rare = frame.rare_campaign.iloc[:train_end].to_numpy()
    ordinary = ~rare
    rows = []
    tree = DecisionTreeRegressor(max_depth=3, random_state=SEED)
    tree.fit(X.iloc[:train_end], y_train)
    error = np.abs(y_train - tree.predict(X.iloc[:train_end]))
    error /= error.max()
    for loss in ("linear", "square", "exponential"):
        transformed = error if loss == "linear" else error**2 if loss == "square" else 1 - np.exp(-error)
        weighted_error = transformed.mean()
        beta = weighted_error / (1 - weighted_error)
        multiplier = beta ** ((1 - transformed) * LEARNING_RATE)
        ordinary_multiplier = multiplier[ordinary].mean()
        rare_multiplier = multiplier[rare].mean()
        rows.append(
            {
                "loss": loss,
                "weighted_error_E": weighted_error,
                "beta": beta,
                "ordinary_mean_multiplier": ordinary_multiplier,
                "rare_campaign_mean_multiplier": rare_multiplier,
                "rare_to_ordinary_ratio": rare_multiplier / ordinary_multiplier,
                "rare_campaign_rows": int(rare.sum()),
            }
        )
    return pd.DataFrame(rows)


def plot_data_overview(export):
    daily = export.set_index("timestamp").resample("D").agg(
        traffic=("traffic", "sum"),
        marketing_event=("marketing_event", "max"),
        rare_campaign=("rare_campaign", "max"),
        attack_like=("attack_like", "max"),
        split=("split", "first"),
    )
    fig, ax = plt.subplots(figsize=(15, 6))
    ax.plot(daily.index, daily.traffic, color="#172554", linewidth=1.8, label="Daily traffic")
    for split, color, label in (("train", "#dbeafe", "Train"), ("validation", "#fef3c7", "Validation"), ("test", "#dcfce7", "Test")):
        subset = daily[daily.split == split]
        if not subset.empty:
            ax.axvspan(subset.index.min(), subset.index.max() + pd.Timedelta(days=1), color=color, alpha=0.55, label=label)
    rare = daily[daily.rare_campaign]
    attack = daily[daily.attack_like]
    ax.scatter(rare.index, rare.traffic, s=80, color="#2563eb", edgecolor="#172554", zorder=4, label="Rare known campaign hour")
    ax.scatter(attack.index, attack.traffic, s=90, color="#f59e0b", edgecolor="#78350f", zorder=5, label="Simulated unexplained spike")
    ax.set(title="The complete 180-day synthetic traffic experiment (daily totals)", xlabel="Date", ylabel="Daily visits")
    ax.annotate(
        "Daily aggregation intentionally dilutes\nthe one-hour unexplained spike.",
        xy=(attack.index[0], attack.traffic.iloc[0]),
        xytext=(-170, 55),
        textcoords="offset points",
        fontsize=10,
        color="#92400e",
        arrowprops={"arrowstyle": "->", "color": "#92400e"},
    )
    ax.legend(ncol=3, frameon=False, loc="upper center", bbox_to_anchor=(0.5, -0.15))
    fig.tight_layout()
    fig.savefig(VISUALS_DIR / "medium_data_overview.png", dpi=180, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def plot_metric_comparison(results):
    test = results[results.split == "test"].copy()
    segments = ["ordinary", "rare_known_campaign", "simulated_attack_like"]
    labels = ["Ordinary traffic", "Rare known campaign", "Simulated unexplained spike"]
    colors = {"linear": "#ef4444", "square": "#2563eb", "exponential": "#7c3aed"}
    y_max = test.mae.max() * 1.18
    fig, axes = plt.subplots(1, 3, figsize=(17, 5.8), constrained_layout=True)
    for ax, segment, label in zip(axes, segments, labels):
        subset = test[test.segment == segment].set_index("loss").loc[["linear", "square", "exponential"]]
        bars = ax.bar(subset.index, subset.mae, color=[colors[loss] for loss in subset.index])
        ax.set_title(label, fontweight="bold")
        ax.set_ylabel("Test MAE")
        ax.set_ylim(0, y_max)
        for bar, value in zip(bars, subset.mae):
            ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + subset.mae.max() * 0.03, f"{value:.1f}", ha="center", fontsize=10)
    fig.suptitle("Aggregate success concealed a costly error slice", fontsize=17, fontweight="bold", y=1.03)
    fig.savefig(VISUALS_DIR / "medium_test_mae_by_segment.png", dpi=180, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def plot_test_results_table(results):
    test = results[results.split == "test"].copy()
    segments = ["ordinary", "rare_known_campaign", "simulated_attack_like"]
    labels = ["Ordinary traffic", "Rare known campaign", "Simulated unexplained spike"]
    losses = ["linear", "square", "exponential"]
    table = test.pivot(index="segment", columns="loss", values="mae").loc[segments, losses]
    rows = []
    for segment, label in zip(segments, labels):
        values = table.loc[segment]
        row_count = int(test[test.segment == segment].iloc[0].n)
        rows.append([label, f"{values['linear']:,.2f}", f"{values['square']:,.2f}", f"{values['exponential']:,.2f}", f"{row_count:,}"])

    fig, ax = plt.subplots(figsize=(13, 3.3))
    ax.axis("off")
    rendered = ax.table(
        cellText=rows,
        colLabels=["Test segment", "Linear MAE", "Square MAE", "Exponential MAE", "Rows"],
        cellLoc="right",
        colLoc="center",
        colWidths=[0.37, 0.15, 0.15, 0.19, 0.10],
        bbox=[0.02, 0.06, 0.96, 0.70],
    )
    rendered.auto_set_font_size(False)
    rendered.set_fontsize(12)
    for (row, column), cell in rendered.get_celld().items():
        cell.set_edgecolor("#d1d5db")
        if row == 0:
            cell.set_facecolor("#1e3a5f")
            cell.set_text_props(color="white", weight="bold", ha="center")
        else:
            cell.set_facecolor("#f8fafc" if row % 2 else "#eaf2fb")
            if column == 0:
                cell.set_text_props(ha="left", weight="bold")
    ax.set_title("Test error by operational segment", fontsize=17, fontweight="bold", pad=16)
    fig.savefig(VISUALS_DIR / "medium_test_results_table.png", dpi=180, bbox_inches="tight", facecolor="white")
    plt.close(fig)


if __name__ == "__main__":
    X, frame = make_data()
    export, results = fit_and_score(X, frame)
    audit = first_round_audit(X, frame)
    export.to_csv(DATA_DIR / "synthetic_hourly_traffic.csv", index=False)
    results.round(6).to_csv(DATA_DIR / "experiment_results.csv", index=False)
    audit.round(6).to_csv(DATA_DIR / "first_round_reweighting_audit.csv", index=False)
    plot_data_overview(export)
    plot_metric_comparison(results)
    plot_test_results_table(results)
    print(f"Wrote data exports to {DATA_DIR}")
    print(f"Wrote Medium visuals to {VISUALS_DIR}")
