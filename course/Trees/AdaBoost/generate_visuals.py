from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.ensemble import AdaBoostRegressor
from sklearn.tree import DecisionTreeRegressor


SEED = 20261023
LEARNING_RATE = 0.05
OUTPUT_DIR = Path(__file__).parent / "visuals"
OUTPUT_DIR.mkdir(exist_ok=True)


def make_data():
    rng = np.random.default_rng(SEED)
    timestamps = pd.date_range("2025-01-01", periods=180 * 24, freq="h", tz="UTC")
    hour = timestamps.hour.to_numpy()
    day_of_week = timestamps.dayofweek.to_numpy()
    day = np.arange(len(timestamps)) // 24
    marketing_event = (day % 21 == 3) | (day % 21 == 4)
    weekend = day_of_week >= 5
    rare_campaign = marketing_event & (hour == 20)
    attack_like = (day == 165) & (hour == 20)
    traffic = (
        920
        + 220 * np.sin(2 * np.pi * (hour - 8) / 24)
        + 100 * (day_of_week < 5)
        + 350 * marketing_event
        + 1600 * rare_campaign
        + rng.normal(0, 55, len(timestamps))
        + 1950 * attack_like
    )
    X = pd.DataFrame(
        {
            "hour_sin": np.sin(2 * np.pi * hour / 24),
            "hour_cos": np.cos(2 * np.pi * hour / 24),
            "dow_sin": np.sin(2 * np.pi * day_of_week / 7),
            "dow_cos": np.cos(2 * np.pi * day_of_week / 7),
            "marketing_event": marketing_event.astype(int),
            "weekend": weekend.astype(int),
        }
    )
    frame = pd.DataFrame(
        {
            "timestamp": timestamps,
            "traffic": traffic,
            "rare_campaign": rare_campaign,
            "attack_like": attack_like,
        }
    )
    return X, frame


def fit_predictions(X, frame):
    train_end = int(0.60 * len(frame))
    output = frame.copy()
    for loss in ("linear", "square"):
        model = AdaBoostRegressor(
            estimator=DecisionTreeRegressor(max_depth=3, random_state=SEED),
            n_estimators=20,
            learning_rate=LEARNING_RATE,
            loss=loss,
            random_state=SEED,
        ).fit(X.iloc[:train_end], frame.traffic.iloc[:train_end])
        output[f"prediction_{loss}"] = model.predict(X)
    return output.iloc[int(0.80 * len(frame)) :].copy()


def make_behaviour_chart(test):
    campaign_time = test.loc[test.rare_campaign, "timestamp"].iloc[0]
    campaign_window = test[
        (test.timestamp >= campaign_time - pd.Timedelta(hours=8))
        & (test.timestamp <= campaign_time + pd.Timedelta(hours=8))
    ]
    attack_time = test.loc[test.attack_like, "timestamp"].iloc[0]
    attack_window = test[
        (test.timestamp >= attack_time - pd.Timedelta(hours=6))
        & (test.timestamp <= attack_time + pd.Timedelta(hours=18))
    ]

    plt.style.use("seaborn-v0_8-whitegrid")
    fig, axes = plt.subplots(1, 2, figsize=(16, 7), constrained_layout=True)
    panels = [
        (axes[0], campaign_window, "Known campaign lift: default creates a false alert", "rare_campaign"),
        (axes[1], attack_window, "Unexplained surge: both models leave a large residual", "attack_like"),
    ]
    for ax, window, title, event_col in panels:
        ax.plot(window.timestamp, window.traffic, color="#172554", linewidth=2.8, label="Observed traffic")
        ax.plot(window.timestamp, window.prediction_linear, color="#ef4444", linewidth=2, linestyle="--", label="Default: linear")
        ax.plot(window.timestamp, window.prediction_square, color="#2563eb", linewidth=2, label="Square loss")
        flagged = window[window[event_col]]
        ax.scatter(flagged.timestamp, flagged.traffic, color="#f59e0b", edgecolor="#78350f", s=72, zorder=5, label="Scenario of interest")
        ax.set_title(title, fontweight="bold", loc="left", fontsize=13)
        ax.set_ylabel("Hourly visits")
        ax.tick_params(axis="x", rotation=28)
    axes[0].annotate("Linear underpredicts a known,\nobservable campaign pattern", xy=(campaign_time, campaign_window.loc[campaign_window.rare_campaign, "traffic"].iloc[0]), xytext=(-150, -95), textcoords="offset points", fontsize=10, color="#991b1b", arrowprops={"arrowstyle": "->", "color": "#991b1b"})
    axes[1].annotate("No feature explains this surge", xy=(attack_time, attack_window.loc[attack_window.attack_like, "traffic"].iloc[0]), xytext=(-145, -100), textcoords="offset points", fontsize=10, color="#92400e", arrowprops={"arrowstyle": "->", "color": "#92400e"})
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="lower center", ncol=4, frameon=False, bbox_to_anchor=(0.5, -0.04))
    fig.suptitle("AdaBoost loss settings change which unusual events the model learns to expect", fontsize=17, fontweight="bold", y=1.03)
    fig.savefig(OUTPUT_DIR / "adaboost_known_vs_unexplained.png", dpi=180, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def make_judgement_chart():
    fig, ax = plt.subplots(figsize=(14, 8))
    ax.set_axis_off()
    boxes = [
        (0.06, 0.61, "Prompt an AI to run AdaBoost", "A model and an aggregate score appear."),
        (0.37, 0.61, "Aggregate MAE looks acceptable", "Default linear loss: ordinary MAE = 59.52"),
        (0.68, 0.61, "Slice errors by operational scenario", "Rare known campaign MAE = 700.65"),
        (0.20, 0.17, "Inspect the error policy", "Square loss prioritises the extreme-error tail."),
        (0.55, 0.17, "Validate the decision", "Known campaign: no false alarm.\nUnexplained surge: review signal remains."),
    ]
    colors = ["#dbeafe", "#e0f2fe", "#fee2e2", "#fef3c7", "#dcfce7"]
    for (x, y, headline, detail), color in zip(boxes, colors):
        ax.text(x, y, headline + "\n\n" + detail, transform=ax.transAxes, ha="left", va="center", fontsize=10.5, linespacing=1.45, bbox={"boxstyle": "round,pad=0.75", "facecolor": color, "edgecolor": "#334155", "linewidth": 1.5})
    arrows = [((0.28, 0.61), (0.36, 0.61)), ((0.59, 0.61), (0.67, 0.61)), ((0.72, 0.49), (0.55, 0.29)), ((0.43, 0.17), (0.54, 0.17))]
    for start, end in arrows:
        ax.annotate("", xy=end, xytext=start, xycoords=ax.transAxes, arrowprops={"arrowstyle": "->", "lw": 2.2, "color": "#475569"})
    fig.suptitle("Running the model is not the same as understanding its behaviour", fontsize=20, fontweight="bold", color="#0f172a", y=0.98)
    fig.text(0.5, 0.88, "The model is not a black box once you inspect assumptions, defaults and error slices.", ha="center", fontsize=13, color="#334155")
    fig.savefig(OUTPUT_DIR / "ai_prompt_vs_model_judgement.png", dpi=180, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def make_loss_calculation_chart():
    error = np.linspace(0, 1, 300)
    linear_loss = error
    square_loss = error**2
    beta = 0.25
    linear_multiplier = beta ** (1 - linear_loss)
    square_multiplier = beta ** (1 - square_loss)

    plt.style.use("seaborn-v0_8-whitegrid")
    fig, axes = plt.subplots(1, 2, figsize=(15, 6), constrained_layout=True)
    axes[0].plot(error, linear_loss, color="#ef4444", linewidth=3, label="linear: L(e) = e")
    axes[0].plot(error, square_loss, color="#2563eb", linewidth=3, label="square: L(e) = e²")
    axes[0].set(title="1. Transform the normalised error", xlabel="Normalised absolute error, e", ylabel="Loss used by AdaBoostRegressor", xlim=(0, 1), ylim=(0, 1.05))
    axes[0].legend(frameon=False, loc="upper left")
    axes[0].annotate("Square downplays middle-sized errors", xy=(0.6, 0.36), xytext=(0.16, 0.62), arrowprops={"arrowstyle": "->", "color": "#475569"}, fontsize=11)

    axes[1].plot(error, linear_multiplier, color="#ef4444", linewidth=3, label="linear")
    axes[1].plot(error, square_multiplier, color="#2563eb", linewidth=3, label="square")
    axes[1].set(title="2. Update the next round's sample weights", xlabel="Normalised absolute error, e", ylabel="Weight multiplier", xlim=(0, 1))
    axes[1].legend(frameon=False, loc="upper left")
    axes[1].annotate("Near-maximum errors are retained\nrelative to middle-sized errors", xy=(0.9, beta ** (1 - 0.9**2)), xytext=(0.30, 0.42), arrowprops={"arrowstyle": "->", "color": "#475569"}, fontsize=11)
    fig.suptitle("AdaBoostRegressor loss is a reweighting policy, not the final prediction metric", fontsize=17, fontweight="bold")
    fig.text(0.5, -0.02, f"Illustration uses beta = {beta:.2f} and learning_rate = {LEARNING_RATE}. In scikit-learn: multiplier = beta^((1 - L(e)) × learning_rate).", ha="center", fontsize=11, color="#334155")
    fig.savefig(OUTPUT_DIR / "adaboost_loss_reweighting.png", dpi=180, bbox_inches="tight", facecolor="white")
    plt.close(fig)


if __name__ == "__main__":
    X, frame = make_data()
    test = fit_predictions(X, frame)
    make_behaviour_chart(test)
    make_judgement_chart()
    make_loss_calculation_chart()
    print(f"Wrote visuals to {OUTPUT_DIR}")
