import numpy as np
import pandas as pd
import sklearn
from sklearn.ensemble import AdaBoostRegressor
from sklearn.metrics import mean_absolute_error, root_mean_squared_error
from sklearn.tree import DecisionTreeRegressor

SEED = 20261023
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
for loss in ("linear", "square", "exponential"):
    model = AdaBoostRegressor(
        estimator=DecisionTreeRegressor(max_depth=3, random_state=SEED),
        n_estimators=20,
        learning_rate=0.05,
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
                        "rmse": root_mean_squared_error(traffic[split][mask], predictions[mask]),
                        "n": int(mask.sum()),
                    }
                )

print(f"scikit-learn: {sklearn.__version__}; seed: {SEED}")
print(pd.DataFrame(rows).round(2).to_string(index=False))
