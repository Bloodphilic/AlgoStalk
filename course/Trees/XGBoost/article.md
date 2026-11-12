# XGBoost Was Not the Answer. It Was the Assumption.

*A powerful classifier can be correctly implemented and still be the wrong first choice — especially when storage is cheap but computation is not.*

**For a separate explanation of boosted-tree mechanics, watch the companion video on [AlgoStalk](https://www.youtube.com/@AlgoStalk). This article is about choosing the model before tuning it.**

When a classification problem arrives, XGBoost is an understandable first suggestion. It is flexible, fast, and very strong on many structured-data problems.

That strength can become a shortcut: “Use XGBoost” arrives before anyone asks what structure is already known in the data — or what the extra flexibility will cost.

## A small classification problem

I built a controlled synthetic example with 730 daily observations. Each day has seasonality, a known campaign plan, and a binary outcome: did demand cross the operational capacity threshold?

The important pattern is a rare but known interaction: a planned campaign launched on a weekend has a much higher probability of crossing the threshold. The campaign plan is available before prediction, so this is a classification problem with an explicit interaction—not an anomaly-detection problem.

The data is split chronologically: 60% training, 20% validation, and 20% untouched test.

## The attractive first result

The initial XGBoost workflow kept trees conservative and selected the lowest aggregate validation accuracy. The winning model used depth-two trees, substantial regularisation, 250 estimators, and a learning rate of 0.04.

Its validation accuracy was **69.2%**. That sounds useful until the class distribution and the operational slice are inspected. The model’s recall for the rare weekend-launch cases was **0%**. It mostly learned that predicting the common class was a safe way to improve accuracy.

This is not an XGBoost bug. It is a model-selection mistake. Accuracy was answering a narrower question than the business was asking.

## The expert question: does this need XGBoost?

The next step was not to launch a larger hyperparameter search. It was to inspect the data-generating structure and decide which error mattered.

The relevant interaction was already known: campaign × weekend. I encoded it explicitly as `weekend_launch`, then compared an interaction-aware XGBoost configuration with a simpler logistic model.

On the untouched chronological test set:

| Model | Accuracy | Balanced accuracy | ROC AUC | Rare-launch recall |
| :-- | --: | --: | --: | --: |
| Constrained XGBoost, aggregate accuracy | 82.2% | 50.0% | 0.537 | 0% |
| Interaction-aware XGBoost, weighted recall | 81.5% | 57.1% | 0.608 | 100% |
| Logistic regression + explicit interaction | **82.9%** | **57.9%** | **0.689** | **100%** |

The simple model won this controlled test. It did not need boosted trees to discover an unknown nonlinear relationship because the relevant relationship had already been expressed in the features. Logistic regression was enough to estimate the relationship and retain the rare positive cases.

## Tune for the error you cannot afford

This is the argument for tuning toward recall rather than accuracy in this example. A false negative means failing to identify a weekend launch likely to cross the capacity threshold. Accuracy rewards the model for getting the much more common ordinary days right, even if it misses the cases that require operational preparation.

That is not a universal rule. If false positives are more expensive, precision may matter more. If both error types matter, balanced accuracy, F-score, or a cost-weighted objective may be more appropriate. For an imbalanced problem, the tuning metric should reflect the decision—not whichever metric produces the most comfortable headline number.

There is also a practical distinction between training and tuning: the classifier can still be trained with a standard probabilistic objective, while hyperparameters and the operating threshold are selected using the business-relevant validation metric. Here, rare-case recall received more weight during selection, and the untouched test set was used only once for the final comparison.

This does not mean logistic regression is generally better than XGBoost. XGBoost is valuable when the boundary is nonlinear, the interactions are numerous or unknown, and feature engineering cannot safely express the structure. It is unnecessary overhead when a transparent model captures the mechanism.

## The cost of choosing capacity by habit

Data storage keeps getting cheaper. That makes it easier to retain more history and create more features. It does not make computation free.

XGBoost multiplies cost across trees, depth, candidate configurations, validation folds, retraining jobs, memory, and—if the model becomes large enough—serving latency. A needlessly complex classifier also creates more work for monitoring, versioning, threshold analysis, and debugging.

Those costs may be justified by a real improvement in the decision metric. They should not be treated as invisible simply because the training run completes successfully.

The expert intervention was straightforward:

- identify the rare interaction rather than accepting aggregate accuracy;
- evaluate recall and balanced accuracy, not accuracy alone;
- compare XGBoost with a transparent model that can express the known structure;
- keep the simpler model because it performed at least as well on untouched data.

The lesson is not “never use XGBoost.” It is: **do not let the availability of a powerful classifier remove the model-selection step — including the cost of the model.**

This is a synthetic stress test, not production evidence. Its purpose is to show a practical boundary: more data availability and more compute do not remove the need to choose the simplest model that meets the decision requirement.

For a separate walkthrough of boosted-tree fundamentals, visit [AlgoStalk on YouTube](https://www.youtube.com/@AlgoStalk).

### References

- [XGBoost parameter documentation](https://xgboost.readthedocs.io/en/stable/parameter.html)
- [XGBoost Python API](https://xgboost.readthedocs.io/en/stable/python/python_api.html)
