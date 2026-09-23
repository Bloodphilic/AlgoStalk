from pathlib import Path

import matplotlib.pyplot as plt
from IPython.display import display


PLOTS_DIR = Path(__file__).resolve().parent / "plots"


def save_plot(fig, filename):
    PLOTS_DIR.mkdir(parents=True, exist_ok=True)
    path = PLOTS_DIR / filename
    fig.savefig(path, dpi=180, bbox_inches="tight", facecolor="white")
    print(path)
    return path


def display_equation(equation, fontsize=24, figsize=(16, 1.2)):
    """Display a transparent equation image in Jupyter without saving it."""
    fig = plt.figure(figsize=figsize)
    fig.patch.set_alpha(0)
    fig.text(0.5, 0.5, equation, ha="center", va="center", fontsize=fontsize)
    plt.axis("off")
    display(fig)
    plt.close(fig)


def display_colored_equation(parts, fontsize=24, figsize=(16, 1.2)):
    """Display a transparent equation made from colored math-text parts."""
    fig, ax = plt.subplots(figsize=figsize)
    fig.patch.set_alpha(0)
    ax.axis("off")

    x = 0.01
    for equation, color in parts:
        text = ax.text(x, 0.5, equation, transform=ax.transAxes,
                       ha="left", va="center", fontsize=fontsize, color=color)
        fig.canvas.draw()
        width = text.get_window_extent(fig.canvas.get_renderer()).width
        x += width / ax.bbox.width

    display(fig)
    plt.close(fig)


def display_matrix(matrix_text, fontsize=28, figsize=(8, 2.8)):
    """Display a transparent matrix image in Jupyter without saving it."""
    fig = plt.figure(figsize=figsize)
    fig.patch.set_alpha(0)
    fig.text(0.5, 0.5, matrix_text, ha="center", va="center",
             fontsize=fontsize, family="DejaVu Sans Mono")
    plt.axis("off")
    display(fig)
    plt.close(fig)


def display_colored_matrix(lines, red_lines=(), fontsize=18, figsize=(18, 3.2)):
    """Display a multiline matrix image with selected rows in red."""
    fig = plt.figure(figsize=figsize)
    fig.patch.set_alpha(0)
    top = 0.9
    step = 0.8 / max(len(lines), 1)
    for index, line in enumerate(lines):
        fig.text(
            0.5,
            top - index * step,
            line,
            ha="center",
            va="center",
            fontsize=fontsize,
            family="DejaVu Sans Mono",
            color="red" if index in red_lines else "black",
        )
    plt.axis("off")
    display(fig)
    plt.close(fig)


def display_table(df, fontsize=14, figsize=(10, 2.2)):
    """Display a clean table image in Jupyter without saving it."""
    fig, ax = plt.subplots(figsize=figsize)
    fig.patch.set_alpha(0)
    ax.axis("off")
    table = ax.table(
        cellText=df.values,
        colLabels=df.columns,
        loc="center",
        cellLoc="center",
        colWidths=[0.9 / len(df.columns)] * len(df.columns),
    )
    table.auto_set_font_size(False)
    table.set_fontsize(fontsize)
    table.scale(1, 1.6)
    for cell in table.get_celld().values():
        cell.set_edgecolor("black")
        cell.set_linewidth(0.6)
    plt.tight_layout()
    display(fig)
    plt.close(fig)


def display_colored_table(df, column_colors, fontsize=12, figsize=(10, 2.2)):
    """Display a table with matching colors for headers and values by column."""
    fig, ax = plt.subplots(figsize=figsize)
    fig.patch.set_alpha(0)
    ax.axis("off")
    table = ax.table(
        cellText=df.values,
        colLabels=df.columns,
        loc="center",
        cellLoc="center",
        colWidths=[0.9 / len(df.columns)] * len(df.columns),
    )
    table.auto_set_font_size(False)
    table.set_fontsize(fontsize)
    table.scale(1, 1.6)
    for (row, col), cell in table.get_celld().items():
        cell.set_edgecolor("black")
        cell.set_linewidth(0.6)
        if col < len(df.columns):
            color = column_colors.get(df.columns[col], "black")
            cell.get_text().set_color(color)
    plt.tight_layout()
    display(fig)
    plt.close(fig)
