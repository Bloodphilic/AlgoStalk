# XGBoost Was Not the Answer. It Was the Assumption.

*A powerful classifier can be correctly implemented and still be the wrong first choice - especially when storage is cheap but computation is not.*

**For a separate explanation of boosted-tree mechanics, watch the companion video on [AlgoStalk](https://www.youtube.com/@AlgoStalk). This article is about the decision that comes before tuning.**

**The short version:** in this synthetic progression-risk experiment, adding one clinically meaningful trajectory interaction to a logistic model produced the best ROC AUC. XGBoost remained useful as a benchmark, but it was not automatically the best tool.

When I see a tabular classification problem, XGBoost is one of the first tools that comes to mind. That instinct is understandable. It is flexible, fast, and very strong on many structured-data problems.

But that strength can become a shortcut: "Use XGBoost" arrives before anyone asks what structure is already known in the data - or what the extra flexibility will cost.

## A synthetic longitudinal example

I wanted an example closer to the kind of work I do, so I built a synthetic progression-risk dataset from a latent-severity process. It contains 1,200 synthetic patient profiles, each with noisy measurements at baseline, 6 months, and 12 months.

The task is to classify whether progression occurs within the next 12 months. The features include baseline motor and cognitive scores, annual rates of decline, tremor change, age, and an imaging-burden summary.

The important pattern is a rare trajectory interaction: rapid motor decline starting from an already impaired baseline. The raw feature table does not contain a single column for that pattern. I derive it afterward for subgroup evaluation, and create an explicit interaction only for the expert comparison.

This is not a clinical model. The data is synthetic: latent disease burden generates noisy observations, and the future outcome is generated from deterioration after the observed period. The example demonstrates a modelling decision, not a medical finding or diagnostic capability.

The patient cohorts are split chronologically: 60% training, 20% validation, and 20% untouched test.

<!-- VISUAL 1 PLACEHOLDER: repeated measurements becoming trajectory features -->
![Synthetic longitudinal motor trajectories](visuals/longitudinal_trajectory_features.png)

*Figure 1. Repeated measurements create trajectory features such as rate of motor decline. Red and grey indicate feature-defined trajectory subgroups, not the progression outcome being classified.*

<!-- VISUAL 2 PLACEHOLDER: baseline motor score against motor decline -->
![Baseline motor score plotted against motor decline](visuals/trajectory_interaction_scatter.png)

*Figure 2. Baseline motor score and motor decline are shown directly for the held-out cohort. Dashed lines show the thresholds used to define the rare trajectory subgroup; colour identifies the subgroup, not the progression outcome.*

## The first model was reasonable

The initial XGBoost search used raw trajectory features and conservative trees. Hyperparameters were selected using aggregate validation accuracy.

That search chose a balanced configuration: depth-three trees, `min_child_weight=20`, subsampling, regularisation, 250 estimators, and a learning rate of 0.04.

On the untouched test cohort, it achieved **87.5% accuracy**, **0.798 balanced accuracy**, and **0.939 ROC AUC**.

Nothing was obviously broken. That is exactly why this kind of result deserves investigation. A model can look acceptable in aggregate while still leaving important questions unanswered: how does it rank risk, how many progression cases does it recover, and what happens in the rare trajectory subgroup?

## The expert question: does this need XGBoost?

The next step was not to launch a much larger hyperparameter search. I went back to the measurement structure and reconsidered both the feature representation and the selection metric.

The rare pattern was already understandable: baseline impairment combined with a sufficiently steep decline. I encoded it as an interaction feature - effectively, low baseline motor score multiplied by rapid motor decline - and compared an interaction-aware XGBoost model with a regularised logistic model.

On the untouched test cohort:

| Model | Accuracy | Balanced accuracy | ROC AUC | Rare-pattern recall |
| :-- | --: | --: | --: | --: |
| XGBoost, aggregate-accuracy search | 87.5% | **79.8%** | 0.939 | 100% |
| XGBoost, interaction-aware tuning | 87.9% | 76.8% | 0.940 | 100% |
| Logistic regression + trajectory interaction | **90.0%** | 80.5% | **0.952** | 100% |

The result is not that logistic regression wins every column. The result is that the transparent model delivered the best accuracy, balanced accuracy, and ranking quality in this controlled experiment, while the XGBoost models did not provide a clear enough gain to justify their additional capacity.

This is important: the expert did not merely tune XGBoost. The intervention changed both the representation of the problem and the definition of success. This is therefore a feature-engineering and model-selection comparison, not a pure hyperparameter-only experiment.

<!-- VISUAL 3 PLACEHOLDER: test-set metric comparison -->
![Comparison of classification metrics](visuals/classification_metric_comparison.png)

*Figure 3. The models are all plausible on aggregate metrics, but the simpler interaction-aware model is strongest in this synthetic test.*

## Tune for the error you cannot afford

For progression-risk screening, recall deserves attention because a false negative may mean that a person who needs review is not flagged. Accuracy alone can hide that cost.

That is not a universal rule. If unnecessary referrals are more expensive, precision matters too. If both errors matter, balanced accuracy, F-score, precision-recall AUC, or a cost-weighted objective may be more suitable.

The important distinction is between training and tuning. A classifier can be trained with a standard probabilistic objective, while hyperparameters and the operating threshold are selected using the metric that reflects the decision. In this experiment, rare-pattern recall was treated as a priority and ROC AUC helped compare ranking quality. The aggregate-accuracy model used the raw features; the expert comparison added the trajectory interaction before fitting.

<!-- VISUAL 4 PLACEHOLDER: rare trajectory recall -->
![Recall on the rare trajectory pattern](visuals/classification_rare_pattern_recall.png)

*Figure 4. All three models recover the six post hoc rare-pattern patients in this held-out sample. That small subgroup is informative, but too small to justify broad clinical claims.*

## The cost of choosing capacity by habit

Data storage keeps getting cheaper. That makes it easier to retain repeated measurements and create more derived features. It does not make computation free.

XGBoost multiplies cost across trees, depth, candidate configurations, validation folds, retraining jobs, memory, and, if the model becomes large enough, serving latency. A needlessly complex classifier also creates more work for monitoring, versioning, threshold analysis, and debugging.

Those costs may be justified by a material improvement in the decision metric. In this experiment, the simpler model was competitive enough that the extra capacity did not clearly earn its place.

The lesson is not "never use XGBoost." It is: **understand the trajectory, define the error that matters, and make the model earn its complexity.**

This is a synthetic stress test, not clinical evidence. I am using it to make one practical point: more data availability and more compute do not remove the need to choose the simplest model that meets the decision requirement.

If you work with longitudinal or imbalanced classification, how do you decide between accuracy, recall, and a cost-weighted metric? I would be interested in hearing how you make that choice.

For the separate walkthrough of boosted-tree fundamentals behind this article, watch [AlgoStalk on YouTube](https://www.youtube.com/@AlgoStalk).

### References

- [XGBoost parameter documentation](https://xgboost.readthedocs.io/en/stable/parameter.html)
- [XGBoost Python API](https://xgboost.readthedocs.io/en/stable/python/python_api.html)
