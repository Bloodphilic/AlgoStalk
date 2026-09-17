from pathlib import Path


PLOTS_DIR = Path(__file__).resolve().parent / "plots"


def save_plot(fig, filename):
    PLOTS_DIR.mkdir(parents=True, exist_ok=True)
    path = PLOTS_DIR / filename
    fig.savefig(path, dpi=180, bbox_inches="tight", facecolor="white")
    print(path)
    return path
