# LightGBM vs XGBoost: The Score Is Not the Decision

*A short churn experiment about thresholds, imbalance, and computational trade-offs.*

**For the walkthrough of the experiment, watch: [YouTube walkthrough: LINK]**

Customer churn is a familiar machine-learning problem, which is exactly why it is easy to do superficially.

The question is not simply: “Can I predict churn?” It is: **which customers should a retention team prioritise, and how many false alarms can the team handle?**

I used IBM's public Telco Customer Churn sample: 7,043 fictional telecom customer records with contract, service, billing, and demographic features. The target is whether the customer churned.

The comparison was deliberately simple: Logistic Regression as a transparent baseline, LightGBM, and XGBoost on the same processed data.

## The evaluation setup

I used a stratified 60/20/20 train, validation, and test split. The identifier column was removed. `TotalCharges` was converted from text to numeric. Missing numeric values were imputed with training-set medians, and categorical values were one-hot encoded using information from the training split only.

That last detail matters. Fitting preprocessing before the split would allow information from the validation or test customers to influence the model.

Churn is the minority class, so accuracy is not enough. I reported PR-AUC, ROC-AUC, and recall at a threshold selected on validation data subject to precision of at least 0.60. The untouched test set was used only for the final report.

<!-- VISUAL 1 PLACEHOLDER: model metric comparison -->
![LightGBM and XGBoost churn metric comparison](visuals/model_comparison.png)

*Figure 1. PR-AUC, ROC-AUC, and recall at the selected operating threshold on the untouched test set.*

## What the numbers say

| Model | PR-AUC | ROC-AUC | Precision | Recall | Train seconds |
| :-- | --: | --: | --: | --: | --: |
| Logistic regression | 0.640 | 0.846 | 0.645 | 0.618 | 0.024 |
| LightGBM | 0.657 | 0.841 | 0.646 | 0.567 | 0.174 |
| XGBoost | **0.666** | **0.849** | 0.644 | 0.580 | 0.434 |

On this split and configuration, XGBoost produced the strongest PR-AUC and ROC-AUC. LightGBM was faster than XGBoost, while the logistic baseline was much faster and remained competitive.

That is a useful result, but not a universal ranking. Changing the split, feature policy, class weighting, threshold constraint, or tuning budget could change the conclusion.

<!-- VISUAL 2 PLACEHOLDER: training time -->
![Training time comparison](visuals/training_time.png)

*Figure 2. Training time is part of the practical model comparison, not an afterthought.*

## Why the implementations differ

LightGBM grows trees leaf-wise: at each step it expands the leaf with the largest loss reduction. This can reach a lower training loss efficiently, but it can also overfit small datasets without suitable constraints.

XGBoost supports different growth policies, including `depthwise` and `lossguide`. The choice affects how tree complexity is allocated. The libraries are both gradient-boosted tree systems, but they are not interchangeable black boxes with identical training behaviour.

<!-- VISUAL 3 PLACEHOLDER: confusion matrices -->
![Churn confusion matrices](visuals/confusion_matrices.png)

*Figure 3. Confusion matrices at each model's validation-selected threshold. The threshold determines how many customers are sent to the retention queue.*

## The practical lesson

The strongest part of this project is not the claim that XGBoost won. It is the evaluation discipline around that claim:

- a simple baseline was included;
- the same customers and preprocessing were used for all models;
- class imbalance was reflected in the metrics;
- the threshold was selected before touching the test set;
- training time was reported alongside predictive performance.

A churn model does not directly tell a business what action to take. It produces a risk score. The business still has to decide how many customers it can contact, what an intervention costs, and whether the intervention actually reduces churn.

This is a compact benchmark using a public fictional dataset. It is not evidence that one boosting library is always better than the other, and it is not a causal analysis of why customers leave.

**[YouTube walkthrough: LINK]**

### Sources

- [IBM Telco Customer Churn sample](https://github.com/IBM/telco-customer-churn-on-icp4d)
- [LightGBM documentation on leaf-wise growth](https://lightgbm.readthedocs.io/en/latest/Features.html)
- [XGBoost parameter documentation](https://xgboost.readthedocs.io/en/stable/parameter.html)
