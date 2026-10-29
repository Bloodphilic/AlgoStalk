import numpy as np
import pandas as pd
import sklearn
from sklearn.ensemble import AdaBoostRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error
from sklearn.tree import DecisionTreeRegressor

SEED = 20261023
LEARNING_RATE = 0.05
rng = np.random.default_rng(SEED)
timestamps = pd.date_range("2025-01-01", periods=180 * 24, freq="h", tz="UTC")
hour = timestamps.hour.to_numpy()
day_of_week = timestamps.dayofweek.to_numpy()
day = np.arange(len(timestamps)) // 24

marketing_event = ((day % 21 == 3) | (day % 21 == 4))
weekend = day_of_week >= 5
rare_campaign_window = marketing_event & (hour == 20)
attack_like = (day == 165) & (hour == 20)

expected_traffic = (
    920
    + 220 * np.sin(2 * np.pi * (hour - 8) / 24)
    + 100 * (day_of_week < 5)
    + 350 * marketing_event
    + 1600 * rare_campaign_window
)
traffic = np.maximum(expected_traffic + rng.normal(0, 55, len(timestamps)) + 1950 * attack_like, 20)

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

n_rows = len(X)
train_end, validation_end = int(0.60 * n_rows), int(0.80 * n_rows)
rows = []
diagnostic_rows = []
for loss in ("linear", "square", "exponential"):
    # Mirror scikit-learn's first-round reweighting from uniform weights so
    # the mechanism is inspectable without replacing the actual experiment.
    diagnostic_estimator = DecisionTreeRegressor(max_depth=3, random_state=SEED)
    initial_weights = np.full(train_end, 1.0 / train_end)
    diagnostic_estimator.fit(X.iloc[:train_end], traffic[:train_end], sample_weight=initial_weights)
    residual = np.abs(traffic[:train_end] - diagnostic_estimator.predict(X.iloc[:train_end]))
    normalized_error = residual / residual.max()
    if loss == "linear":
        transformed_loss = normalized_error
    elif loss == "square":
        transformed_loss = normalized_error**2
    else:
        transformed_loss = 1.0 - np.exp(-(normalized_error**2))
    weighted_error = np.average(transformed_loss, weights=initial_weights)
    beta = weighted_error / (1.0 - weighted_error)
    multipliers = beta ** ((1.0 - transformed_loss) * LEARNING_RATE)
    for segment, mask in {
        "ordinary": ~marketing_event[:train_end] & ~rare_campaign_window[:train_end],
        "rare_known_campaign": rare_campaign_window[:train_end],
    }.items():
        diagnostic_rows.append(
            {
                "loss": loss,
                "weighted_error_E": weighted_error,
                "beta": beta,
                "segment": segment,
                "mean_normalized_error": normalized_error[mask].mean(),
                "mean_weight_multiplier": multipliers[mask].mean(),
                "n": int(mask.sum()),
            }
        )
    model = AdaBoostRegressor(
        estimator=DecisionTreeRegressor(max_depth=3, random_state=SEED),
        n_estimators=20,
        learning_rate=LEARNING_RATE,
        loss=loss,
        random_state=SEED,
    ).fit(X.iloc[:train_end], traffic[:train_end])
    for split_name, split in (("validation", slice(train_end, validation_end)), ("test", slice(validation_end, n_rows))):
        predictions = model.predict(X.iloc[split])
        segments = {
            "ordinary": ~marketing_event[split] & ~attack_like[split],
            "rare_known_campaign": rare_campaign_window[split],
            "simulated_attack_like": attack_like[split],
        }
        for name, mask in segments.items():
            if mask.any():
                rows.append(
                    {
                        "split": split_name,
                        "loss": loss,
                        "segment": name,
                        "mae": mean_absolute_error(traffic[split][mask], predictions[mask]),
                        "rmse": np.sqrt(mean_squared_error(traffic[split][mask], predictions[mask])),
                        "n": int(mask.sum()),
                    }
                )

print(f"scikit-learn: {sklearn.__version__}; seed: {SEED}")
print("\nFirst-round reweighting audit (mirrors AdaBoostRegressor's initial uniform weights):")
print(pd.DataFrame(diagnostic_rows).round(4).to_string(index=False))
print(pd.DataFrame(rows).round(2).to_string(index=False))
