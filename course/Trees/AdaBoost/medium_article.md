# The Model Was Running Fine. The Problem Was What Its Defaults Meant.

*A reproducible AdaBoostRegressor case study on alert quality, loss functions, and why an AI-generated baseline is not the end of the investigation.*

> **Before you continue:** for a visual explanation of how AdaBoost works, watch the companion video on the [AlgoStalk YouTube channel](https://www.youtube.com/@AlgoStalk). This article does not repeat that fundamentals lesson. It investigates one operational consequence of AdaBoostRegressor's `loss` setting.

## The hard part is not finding a spike

The hard part is deciding which spikes deserve human attention.

An AI agent can instantiate an estimator, run a notebook, and report a reasonable aggregate score in seconds. That is useful. It is also incomplete. A model can run without errors while creating the wrong alerts: asking people to investigate known, legitimate behaviour while offering no extra clarity on genuinely unexplained behaviour.

I built a small, fully reproducible traffic experiment to make that distinction concrete. The result is not a claim about any production system or security incident. The data are synthetic by design, because the real site data and implementation cannot be published. The values, charts, calculations, and outputs below are from the actual deterministic synthetic experiment in this project—not invented examples after the fact.

The operational objective is narrow:

> Estimate expected hourly traffic from known inputs. Route unusually large residuals to human review. Do not treat a residual as an attack classification.

The experiment contains a rare but legitimate campaign pattern and a separate simulated unexplained spike. The question is not whether a model can see a high number. It is whether it learns the known pattern well enough that human attention remains available for the unknown one.

![A workflow from an AI-generated model and acceptable aggregate MAE to scenario-level error inspection, reweighting-policy review, and an alerting decision.](visuals/ai_prompt_vs_model_judgement.png)

*Figure 1. Running a model is not the same as understanding its behaviour.*

## The data: a controlled hourly traffic experiment

The dataset has 4,320 hourly observations: 180 days beginning 1 January 2025. It includes daily seasonality, weekday effects, Gaussian noise, and recurring two-day marketing events every 21 days.

Most marketing events add a modest lift. A rarer interaction adds a much larger but legitimate lift: the campaign is active, the time is 8pm, and the event falls on its scheduled weekend. Those inputs are available to the model. This matters: the model is not expected to infer an unrecorded cause.

In the held-out test period, I add one similarly sized one-hour simulated surge with no explanatory feature. It is deliberately separate from the campaign mechanism. The model is not given an “attack” column or a hidden proxy for it.

| Item | Configuration |
|---|---|
| Observations | 4,320 hourly rows / 180 days |
| Target | Hourly website visits |
| Features | Hour-of-day sine/cosine, day-of-week sine/cosine, marketing-event flag, weekend flag |
| Legitimate rare pattern | Campaign event at 8pm on its event weekend |
| Simulated unexplained pattern | One held-out hourly spike, with no explanatory feature |
| Split | Chronological: 60% train / 20% validation / 20% test |
| Seed | 20261023 |

![The complete 180-day synthetic traffic experiment, with chronological train, validation and test periods, rare known campaign hours, and a simulated unexplained spike.](visuals/medium_data_overview.png)

*Figure 2. The full 180-day synthetic experiment shown as daily totals. Blue points identify rare known campaign hours; orange identifies the held-out unexplained spike. Daily aggregation deliberately makes a one-hour spike less prominent; Figure 5 shows the same observations at hourly resolution.*


## The fixed model comparison

I used scikit-learn 1.9.0's `AdaBoostRegressor` with a fixed shallow base tree:

```python
AdaBoostRegressor(
    estimator=DecisionTreeRegressor(max_depth=3, random_state=20261023),
    n_estimators=20,
    learning_rate=0.05,
    loss=loss,                 # linear, square, or exponential
    random_state=20261023,
)
```

Everything except `loss` stayed fixed: data, features, chronological split, base-tree depth, estimator count, learning rate, and random seed. This isolates the decision under investigation. The validation slice confirmed the pattern; the final numbers below come from the untouched test period.

## Why `loss` matters inside AdaBoostRegressor

AdaBoostRegressor does not simply fit a larger tree when it makes a mistake. It fits shallow regressors sequentially. After each round, it changes the distribution from which the next learner is trained.

For a given round, scikit-learn takes the absolute residual and normalises it by that round's largest residual. Call the result `e`, where `0 <= e <= 1`. The relevant transformations are:

```text
linear: L(e) = e
square: L(e) = e^2
```

It then computes weighted round error `E`, defines `beta = E / (1 - E)`, and updates the sample weight using:

```text
weight *= beta ** ((1 - L(e)) * learning_rate)
```

Because `beta` is below one, a higher transformed loss means that example is downweighted less for the next round. The point is subtle: square loss does not simply make every error “more important.” It downplays middle-sized normalised errors relative to errors near the maximum.

At `e = 0.6`, linear gives 0.60 and square gives 0.36. At `e = 0.9`, they give 0.90 and 0.81. The setting changes which mistakes later trees are built to address.

![Linear and square loss transformations and their resulting illustrative sample-weight multipliers over normalised prediction error.](visuals/adaboost_loss_reweighting.png)

*Figure 3. In AdaBoostRegressor, `loss` is a reweighting policy, not the final prediction metric.*

## The result that an aggregate report can hide

The default `loss='linear'` looked serviceable on ordinary test traffic: MAE 59.52. A quick model report could stop there.

That would miss the operational failure. On the rare, known campaign slice, linear loss produced MAE 700.65. The model would have treated expected business activity as a major deviation from expectation.

Square loss changed that picture. Its ordinary-traffic MAE was only slightly higher at 60.81, while rare-campaign MAE fell to 41.31. Exponential loss did not help that rare slice.

| Test segment | Linear MAE | Square MAE | Exponential MAE | Rows |
|---|---:|---:|---:|---:|
| Ordinary traffic | 59.52 | 60.81 | 59.36 | 767 |
| Rare known campaign | 700.65 | 41.31 | 760.29 | 4 |
| Simulated unexplained spike | 1,814.33 | 1,811.42 | 1,810.30 | 1 |

The last row is important. Changing loss did not “detect an attack.” The unexplained spike remains a large residual under every setting because no model input explains it. It is a review signal, not proof of a cause.

![Test mean absolute error by loss function for ordinary traffic, rare known campaign traffic, and the simulated unexplained spike.](visuals/medium_test_mae_by_segment.png)

*Figure 4. Similar ordinary-traffic performance concealed a dramatically different outcome on the rare legitimate pattern.*

## What the two spikes show

The final visual is the practical result in miniature.

On the left, the observed campaign spike is legitimate and feature-defined. Linear loss materially underpredicts it; square loss predicts it closely. A residual-based alert system built on the linear model could waste human attention on an event the available inputs should make predictable.

On the right, the observed spike is intentionally unexplained. Neither model has a causal input that would allow it to forecast the lift. Both predictions remain near expected traffic and both residuals remain large. That is the behaviour wanted from this controlled setup.

![Side-by-side traffic charts. Square loss predicts the known campaign spike more closely than linear loss; both leave the unexplained spike as a large residual.](visuals/adaboost_known_vs_unexplained.png)

*Figure 5. Square loss learns the rare known campaign pattern without normalising the unexplained spike.*

## What an AI agent can do - and what it cannot decide for you

An AI agent can generate the code, execute the default model, compare options, and surface the metric table. Those are meaningful capabilities. But the agent does not automatically know that false alarms during rare campaigns are costly, or that an unexplained residual should lead to review rather than a claim of attack. Those are problem-definition and decision-design choices.

This is where experienced data-science judgement matters: inspect defaults, understand the training mechanism, ask which slice carries operational cost, and keep a held-out test period intact. “The model ran” and “the model supports the decision” are different statements.

If you want the foundational walkthrough before applying this idea to a case study, watch the AdaBoost companion video on the [AlgoStalk YouTube channel](https://www.youtube.com/@AlgoStalk). The video explains the mechanics; this article shows why those mechanics matter when a model enters an alerting workflow.

## Limits of this demonstration

This is a controlled synthetic stress test. It deliberately creates a rare interaction for a shallow ensemble to learn. The result does not establish that square loss will outperform linear loss on another site, another target, or a production system.

The simulated spike is not an attack label. In practice, a high residual could reflect an unlogged campaign, instrumentation error, a release, automated traffic, or a genuine incident. It should trigger investigation, not a causal conclusion.

The correct lesson is narrower and more useful: defaults are starting points. In AdaBoostRegressor, `loss` defines part of the error-reweighting policy. If the cost of errors is asymmetric or concentrated in a rare operating scenario, inspect that behaviour directly rather than trusting a single aggregate number.

---

## Reproducibility and sources

Generate the complete assets from the repository root:

```powershell
python course\Trees\AdaBoost\run_experiment.py
python course\Trees\AdaBoost\generate_visuals.py
python course\Trees\AdaBoost\generate_medium_assets.py
```

Generated data and results:

- `medium_data/synthetic_hourly_traffic.csv`
- `medium_data/experiment_results.csv`
- `medium_data/first_round_reweighting_audit.csv`

Primary references:

- [scikit-learn: AdaBoostRegressor API and source](https://scikit-learn.org/stable/modules/generated/sklearn.ensemble.AdaBoostRegressor.html)
- [Drucker, Improving Regressors using Boosting Techniques (1997)](https://dl.acm.org/doi/10.5555/645526.657132)
