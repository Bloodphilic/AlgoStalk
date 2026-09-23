import matplotlib.pyplot as plt


def get_market_chart(
    df,
    x_column,
    y_columns,
    label=None,
    color=None,
    ax=None,
    normalize=False,
    hide_ticks=True,
):
    """Plot one or more columns, optionally normalized for comparison."""
    if isinstance(y_columns, str):
        y_columns = [y_columns]

    if ax is None:
        _, ax = plt.subplots(figsize=(15, 6))

    for column in y_columns:
        values = df[column]

        if normalize == "zscore":
            values = (values - values.mean()) / values.std()
        elif normalize:
            first_value = values.dropna().iloc[0]
            values = values / first_value * 100

        line_label = label if label and len(y_columns) == 1 else column
        if isinstance(color, dict):
            line_color = color.get(column)
        elif isinstance(color, (list, tuple)):
            line_color = color[y_columns.index(column)]
        else:
            line_color = color
        ax.plot(df[x_column], values, label=line_label, color=line_color)

    if hide_ticks:
        ax.set_xticks([])
        ax.set_yticks([])

    ax.legend()
    return ax
