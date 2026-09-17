# AlgoStalk

Python environment for the AlgoStalk analysis notebooks and scripts.

## Setup

Install [uv](https://docs.astral.sh/uv/), then from this directory run:

```sh
uv sync
```

## Start JupyterLab

```sh
uv run jupyter lab
```

Open `course/TimeSeries/VAR/code/VAR_Concepts_Investigation.ipynb` in JupyterLab.

## Run the VAR market data fetcher

From this directory:

```sh
uv run python course/TimeSeries/VAR/code/fetch_market_data.py
```

The fetcher needs network access and saves the CSV under the VAR `code/data/` directory.
