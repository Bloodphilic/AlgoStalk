"""Fit SARIMA to synthetic daily demand and generate article visuals."""

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from statsmodels.tsa.statespace.sarimax import SARIMAX

SEED = 20261113
ROOT = Path(__file__).parent
VISUALS = ROOT / "visuals"
DATA = ROOT / "data"
TRAIN_SIZE = 1088
SEASONAL_PERIOD = 7
FORECAST_HORIZON = 14


def make_series():
    rng = np.random.default_rng(SEED)
    date = pd.date_range("2024-01-01", periods=TRAIN_SIZE + FORECAST_HORIZON, freq="D")
    t = np.arange(len(date))
    level = 1000.0 + 0.08 * t
    weekly = 125 * np.sin(2 * np.pi * t / 7) + 35 * np.sin(4 * np.pi * t / 7)
    innovations = rng.normal(0, 26, len(t))
    dynamic = np.zeros(len(t))
    for i in range(1, len(t)):
        dynamic[i] = 0.48 * dynamic[i - 1] + innovations[i]
    demand = level + weekly + dynamic
    return pd.DataFrame({"date": date, "demand": demand})


def save(fig, filename):
    fig.savefig(VISUALS / filename, dpi=180, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def acf(values, max_lag):
    values = np.asarray(values)
    values = values - values.mean()
    denominator = np.dot(values, values)
    return np.array([np.dot(values[:-lag], values[lag:]) / denominator for lag in range(1, max_lag + 1)])


def main():
    frame = make_series()
    DATA.mkdir(exist_ok=True)
    VISUALS.mkdir(exist_ok=True)
    frame.to_csv(DATA / "synthetic_daily_electricity_demand.csv", index=False)

    train = frame.iloc[:TRAIN_SIZE].copy()
    test = frame.iloc[TRAIN_SIZE:].copy()

    fig, ax = plt.subplots(figsize=(13, 4), constrained_layout=True)
    ax.plot(train.date, train.demand, color="#334155", linewidth=0.8, label="Training demand")
    ax.plot(test.date, test.demand, color="#dc2626", linewidth=2, label="Held-out seasonal cycle")
    ax.axvline(test.date.iloc[0], color="#64748b", linestyle="--", linewidth=1)
    ax.axvspan(test.date.iloc[0], test.date.iloc[-1], color="#fecaca", alpha=0.35)
    ax.set_title("Training window and two-week evaluation horizon", fontweight="bold")
    ax.set_xlabel("Date")
    ax.set_ylabel("Demand")
    ax.legend()
    ax.grid(alpha=0.2)
    save(fig, "step_1_series_split.png")

    weekday_profile = train.assign(weekday=train.date.dt.day_name()).groupby("weekday", sort=False)["demand"].mean()
    ordered_days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    profile = weekday_profile.reindex(ordered_days)
    fig, axes = plt.subplots(1, 2, figsize=(12, 4), constrained_layout=True)
    axes[0].bar(profile.index.str[:3], profile.values, color="#059669")
    axes[0].set_title("Mean demand by weekday", fontweight="bold")
    axes[0].set_ylabel("Demand")
    axes[1].stem(np.arange(1, 29), acf(train.demand.values, 28), linefmt="#2563eb", markerfmt="o", basefmt=" ")
    axes[1].axvline(7, color="#dc2626", linestyle="--", linewidth=1, label="Weekly lag")
    axes[1].set_title("Autocorrelation at seasonal lags", fontweight="bold")
    axes[1].set_xlabel("Lag (days)")
    axes[1].set_ylabel("Autocorrelation")
    axes[1].legend()
    for ax in axes:
        ax.grid(alpha=0.2)
    save(fig, "step_2_seasonal_period.png")

    ordinary_difference = train.demand.diff()
    seasonal_difference = train.demand.diff(SEASONAL_PERIOD)
    fig, axes = plt.subplots(3, 1, figsize=(13, 7), sharex=True, constrained_layout=True)
    recent = train.iloc[-180:]
    axes[0].plot(recent.date, recent.demand, color="#94a3b8", linewidth=0.8)
    axes[0].set_title("Original demand: final 180 training days", fontweight="bold")
    axes[1].plot(train.date, ordinary_difference, color="#7c3aed", linewidth=0.7)
    axes[1].set_title("Ordinary difference: y(t) - y(t-1)", fontweight="bold")
    axes[2].plot(train.date, seasonal_difference, color="#d97706", linewidth=0.7)
    axes[2].set_title("Seasonal difference: y(t) - y(t-7)", fontweight="bold")
    for ax in axes:
        ax.grid(alpha=0.2)
    axes[2].set_xlabel("Date")
    save(fig, "step_3_differencing.png")

    model = SARIMAX(
        train.demand,
        order=(1, 1, 1),
        seasonal_order=(1, 1, 1, SEASONAL_PERIOD),
        enforce_stationarity=False,
        enforce_invertibility=False,
    )
    fitted = model.fit(disp=False)
    fitted_values = fitted.fittedvalues
    residuals = fitted.resid.dropna()

    fig, axes = plt.subplots(2, 1, figsize=(13, 6.5), constrained_layout=True)
    axes[0].plot(train.date.iloc[-180:], train.demand.iloc[-180:], color="#334155", linewidth=0.9, label="Actual")
    axes[0].plot(train.date.iloc[-180:], fitted_values.iloc[-180:], color="#2563eb", linewidth=1.1, label="SARIMA fitted")
    axes[0].set_title("SARIMA fit near the forecast boundary", fontweight="bold")
    axes[0].legend()
    axes[1].stem(np.arange(1, 29), acf(residuals.values, 28), linefmt="#dc2626", markerfmt="o", basefmt=" ")
    axes[1].axhline(0, color="#64748b", linewidth=0.7)
    axes[1].set_title("Residual autocorrelation", fontweight="bold")
    axes[1].set_xlabel("Lag (days)")
    axes[1].set_ylabel("Autocorrelation")
    for ax in axes:
        ax.grid(alpha=0.2)
    save(fig, "step_4_model_diagnostics.png")

    prediction = fitted.get_forecast(steps=FORECAST_HORIZON)
    forecast = prediction.predicted_mean
    interval = prediction.conf_int()
    fig, ax = plt.subplots(figsize=(13, 4.5), constrained_layout=True)
    context = train.iloc[-60:]
    ax.plot(context.date, context.demand, color="#334155", linewidth=0.9, label="Training demand")
    ax.plot(test.date, test.demand, color="#dc2626", linewidth=2, label="Held-out actual")
    ax.plot(test.date, forecast.values, color="#2563eb", linewidth=2, marker="o", label="SARIMA forecast")
    ax.fill_between(test.date, interval.iloc[:, 0], interval.iloc[:, 1], color="#93c5fd", alpha=0.35, label="95% interval")
    ax.axvline(test.date.iloc[0], color="#64748b", linestyle="--", linewidth=1)
    ax.set_title("Forecasting two complete weekly cycles", fontweight="bold")
    ax.set_xlabel("Date")
    ax.set_ylabel("Demand")
    ax.legend()
    ax.grid(alpha=0.2)
    save(fig, "step_5_forecast.png")

    errors = test.demand.to_numpy() - forecast.to_numpy()
    mae = float(np.mean(np.abs(errors)))
    rmse = float(np.sqrt(np.mean(errors ** 2)))
    fig, ax = plt.subplots(figsize=(8, 4), constrained_layout=True)
    colors = ["#dc2626" if error < 0 else "#2563eb" for error in errors]
    ax.bar(test.date.dt.strftime("%a"), errors, color=colors)
    ax.axhline(0, color="#334155", linewidth=0.8)
    ax.set_title(f"Held-out forecast errors | MAE={mae:.2f}, RMSE={rmse:.2f}", fontweight="bold")
    ax.set_ylabel("Actual - forecast")
    ax.grid(axis="y", alpha=0.2)
    save(fig, "step_6_errors.png")

    (ROOT / "sarima_metrics.txt").write_text(
        f"model=SARIMA(1,1,1)(1,1,1,7)\n"
        f"train_rows={len(train)}\nforecast_rows={len(test)}\n"
        f"mae={mae:.6f}\nrmse={rmse:.6f}\n",
        encoding="utf-8",
    )
    print(f"Rows={len(frame)}; train={len(train)}; horizon={len(test)}; seed={SEED}")
    print(f"MAE={mae:.3f}; RMSE={rmse:.3f}")
    print(f"Wrote {DATA / 'synthetic_daily_electricity_demand.csv'}")
    print(f"Wrote SARIMA visuals and metrics to {ROOT}")


if __name__ == "__main__":
    main()
