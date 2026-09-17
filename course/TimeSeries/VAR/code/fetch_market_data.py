"""Fetch the most recent two years of daily market data from Yahoo Finance.

Instruments: Gold, Silver, Crude Oil, S&P 500, Bitcoin, and the U.S. Dollar Index.
Uses Yahoo Finance chart data via its public endpoint and Python standard library.
"""
from __future__ import annotations

import csv
import json
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

TICKERS = {
    "Gold": "GC=F",       # Gold futures
    "Silver": "SI=F",     # Silver futures
    "Oil": "CL=F",        # WTI crude oil futures
    "SP500": "^GSPC",     # S&P 500 index
    "BTC": "BTC-USD",     # Bitcoin in USD
    "DXY": "DX-Y.NYB",    # U.S. Dollar Index
}

BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "data"
OUTPUT_CSV = OUTPUT_DIR / "market_data_2y_daily.csv"


def fetch_chart(ticker: str, start: datetime, end: datetime) -> list[dict]:
    """Fetch daily OHLCV observations for one Yahoo Finance ticker."""
    period1 = int(start.timestamp())
    period2 = int(end.timestamp())
    url = (
        f"https://query1.finance.yahoo.com/v8/finance/chart/{quote(ticker, safe='')}"
        f"?period1={period1}&period2={period2}&interval=1d&events=history"
    )
    request = Request(url, headers={"User-Agent": "Mozilla/5.0 market-research-notebook"})
    with urlopen(request, timeout=30) as response:
        payload = json.loads(response.read().decode("utf-8"))

    result = payload.get("chart", {}).get("result")
    error = payload.get("chart", {}).get("error")
    if error:
        raise RuntimeError(f"Yahoo Finance error for {ticker}: {error}")
    if not result:
        raise RuntimeError(f"No data returned for {ticker}")

    chart = result[0]
    timestamps = chart.get("timestamp", [])
    quote_data = chart["indicators"]["quote"][0]
    adjusted = chart["indicators"].get("adjclose", [{}])[0].get("adjclose", [])
    rows = []
    for i, timestamp in enumerate(timestamps):
        row = {
            "Date": datetime.fromtimestamp(timestamp, timezone.utc).date().isoformat(),
            "Market": next(name for name, symbol in TICKERS.items() if symbol == ticker),
            "Ticker": ticker,
            "Open": quote_data.get("open", [None] * len(timestamps))[i],
            "High": quote_data.get("high", [None] * len(timestamps))[i],
            "Low": quote_data.get("low", [None] * len(timestamps))[i],
            "Close": quote_data.get("close", [None] * len(timestamps))[i],
            "AdjClose": adjusted[i] if i < len(adjusted) else None,
            "Volume": quote_data.get("volume", [None] * len(timestamps))[i],
        }
        rows.append(row)
    return rows


def fetch_all(output_path: Path = OUTPUT_CSV) -> Path:
    """Download two years of daily data and save a tidy CSV."""
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=5 * 365 + 1)
    all_rows: list[dict] = []
    for market, ticker in TICKERS.items():
        print(f"Fetching {market} ({ticker})…")
        try:
            all_rows.extend(fetch_chart(ticker, start, end))
        except (HTTPError, URLError, TimeoutError, RuntimeError, KeyError, ValueError) as exc:
            raise RuntimeError(f"Failed to fetch {market} ({ticker}): {exc}") from exc
        time.sleep(0.25)  # keep requests spaced out

    output_path.parent.mkdir(parents=True, exist_ok=True)
    columns = ["Date", "Market", "Ticker", "Open", "High", "Low", "Close", "AdjClose", "Volume"]
    with output_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        writer.writerows(all_rows)
    print(f"Saved {len(all_rows):,} observations to {output_path}")
    return output_path


if __name__ == "__main__":
    fetch_all()
