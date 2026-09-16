#!/usr/bin/env python3
"""
Dividend profile fetcher for income buy plans.

Emits JSON keyed by ticker with the fields an income ordering needs:
  p          -- current price
  y          -- dividend yield (%)
  rate       -- annual dividend $/share
  pay_months -- ACTUAL months dividends landed in the trailing ~400 days.
                This is what determines the payout cycle. Never guess it.
  payout     -- payout ratio (see REIT caveat below)
  div_cagr5  -- 5-year dividend CAGR (%), computed on full calendar years

Usage:
    python dividend_profile.py > divdata.json
    python dividend_profile.py AAPL MSFT O > divdata.json

Interpreting the output (these cost a session to learn):

  * payout > 1.0 on a REIT is NORMAL. REITs are measured on AFFO, not GAAP EPS.
    Realty Income (O) reported 265% here while its AFFO payout was ~75%.

  * div_cagr5 < 0 means one of two very different things:
      (a) the dividend was CUT  -> hard exclude from an income plan (e.g. MMM)
      (b) a variable SPECIAL dividend distorts the series -> the real all-in
          yield may be much HIGHER than `y` (e.g. CME)
    Disambiguate by looking at whether the series has irregular large payments,
    not by trusting the CAGR number alone.

  * pay_months mapping to cycles:
      [1,4,7,10] -> Cycle 1 (JAJO)
      [2,5,8,11] -> Cycle 2 (FMAN)
      [3,6,9,12] -> Cycle 3 (MJSD)
      all twelve -> true monthly payer, rank first in an income ordering
    Some names straddle (e.g. [3,5,8,11]); assign by majority and note it.

Writing the output: on Windows, do NOT pipe results into `printf` when the text
contains paths like C:\\Users\\... -- bash eats \\U and \\v. Use write_file.
"""

import json
import sys

import pandas as pd
import yfinance as yf

DEFAULT_TICKERS = [
    "ABT", "TMO", "DHR", "DE", "ITW", "EMR", "PH", "CME", "ROP", "O",
    "PEP", "CVX", "V", "MA", "SPGI", "MCO", "LIN", "SHW", "TXN", "NEE",
    "KO", "JNJ", "PG", "MMM", "AXP", "IBM", "CL", "XOM", "CAT", "JPM",
    "WMT", "MCD",
]

CYCLES = {
    (1, 4, 7, 10): "1 (JAJO)",
    (2, 5, 8, 11): "2 (FMAN)",
    (3, 6, 9, 12): "3 (MJSD)",
}


def classify_cycle(months):
    """Map observed pay months to a payout cycle label."""
    if len(months) >= 11:
        return "MONTHLY"
    exact = CYCLES.get(tuple(sorted(months)))
    if exact:
        return exact
    # Straddling name: assign by majority membership.
    best, score = "mixed", 0
    for key, label in CYCLES.items():
        overlap = len(set(months) & set(key))
        if overlap > score:
            best, score = label, overlap
    return best if score >= 3 else "mixed"


def dividend_cagr(dividends, years=5):
    """5y dividend CAGR on full calendar-year totals. None if insufficient data."""
    totals = {}
    for dt, val in dividends.items():
        totals[dt.year] = totals.get(dt.year, 0) + val
    # Drop the current (partial) year, then take the trailing window.
    complete = sorted(totals)[:-1]
    window = complete[-(years + 1):]
    if len(window) < 2:
        return None
    first, last = totals[window[0]], totals[window[-1]]
    if first <= 0:
        return None
    return round(((last / first) ** (1 / (len(window) - 1)) - 1) * 100, 1)


def profile(symbol):
    tk = yf.Ticker(symbol)
    info = tk.info
    divs = tk.dividends

    months, cycle, cagr = [], "none", None
    if len(divs):
        recent = divs[divs.index >= (divs.index[-1] - pd.Timedelta(days=400))]
        months = sorted({d.month for d in recent.index})
        cycle = classify_cycle(months)
        cagr = dividend_cagr(divs)

    return {
        "p": info.get("currentPrice"),
        "y": info.get("dividendYield"),
        "rate": info.get("dividendRate"),
        "pay_months": months,
        "cycle": cycle,
        "payout": info.get("payoutRatio"),
        "div_cagr5": cagr,
    }


def main():
    tickers = sys.argv[1:] or DEFAULT_TICKERS
    out = {}
    for sym in tickers:
        try:
            out[sym] = profile(sym)
        except Exception as exc:  # keep going; one bad ticker shouldn't kill the run
            out[sym] = {"error": str(exc)}
    print(json.dumps(out, indent=1, default=str))


if __name__ == "__main__":
    main()
