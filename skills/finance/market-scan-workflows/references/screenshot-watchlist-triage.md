# Screenshot Watchlist Triage

Class of task: user pastes a screenshot of a screener/watchlist grid and asks
"which is best to buy today, backtest the idea". Often adds a framing claim
("most are penny stocks") that must be CHECKED, not accepted.

## 1. Get the tickers out of the image

Try `vision_analyze` first. If it errors (404 / provider down), fall back to
the Windows built-in OCR engine — no install required:

    scripts/windows_ocr.ps1  (in this skill)

Pitfalls that cost real time:
- Raw-resolution OCR on a dense screener grid returns garbage
  ("Sa _ 21", "SS _ 49"). ALWAYS greyscale + upscale 3-6x with PIL LANCZOS first.
- Even upscaled, the NUMERIC columns OCR badly. Do not try to read prices out
  of the image — you only need the TICKERS. Crop the left ~30% of the image
  and upscale that 6x; ticker symbols come back clean. Re-fetch every number
  from yfinance.
- Multiple attached screenshots are frequently the SAME image (check byte
  size). Don't OCR duplicates.

## 2. Re-derive all metrics from data, never from the screenshot

Pull 2y daily for the whole list in one `yf.download(..., group_by="ticker")`.
Compute: price, gap%, rel_vol vs 50d, dollar volume, SMA/EMA 50/200 posture,
1/3/6/12m returns, ATR14 and ATR%, annualised vol, 1y max drawdown,
distance from 52w high.

Check the user's framing. In the 2026-08-07 run the user said "most are penny
stocks"; only 3 of 11 were sub-$5 and the median was ~$7. Say so plainly.

## 3. Apply the standing gates BEFORE forming an opinion

- STOCK hard-gate: rel_vol >= 4x 50d AND longs gap up. This alone eliminated
  7 of 11 names.
- News-protocol 30M volume floor (see `news-high-volume-trade-protocol`).
- Dollar-volume sanity: a name can pass 6x rel_vol and still be uninvestable
  (KRO passed at 6.06x but trades only $3.0M/day).
- Foreign names may be US ADRs with a fraction of the home-line volume
  (WPP ADR ~530k/day vs the LSE line). Say "buy the LSE line", don't just
  fail it silently.

## 4. Backtest the SETUP, not the ticker

The idea being tested is "buy a rel_vol>=4x + gap-up day at the close".
Replay exactly that on 10y of each name's own history, pooled and per-name,
across a hold grid (1/3/5/10d). Report n, win%, avg, median, PF, t-stat.

This is where the value is. In the 2026-08-07 run the pooled 10d leg was
PF 2.25 / t=2.15, but per-name the backtest VETOED two names the momentum
screen liked: GDRX at PF 0.04 / t=-3.87 (it systematically fades its gaps)
and HTZ at PF 0.53 / 25% win. Neither would have been caught by the gate.

Grade the result against the user's 3-TEST PROOF BAR (10y PF>=1.0 AND
walk-fwd OOS PF>=1 AND grid >=50% AND p<0.05). If it only partly clears,
call it AMBER explicitly and say "do not size this like a GREEN_PROVEN edge".
Never let a single significant hold-length imply the whole idea is proven.

## 5. Verify the catalyst by hand

blogwatcher coverage is crypto-only, so the per-symbol sentiment layer is
unavailable for equities — state that, then web-search each finalist's
catalyst. Distinguish a hard fundamental beat (IOVA: record Q2 revenue,
margin expansion) from an unexplained squeeze on a broken chart (HTZ: no
catalyst found, -57.7% below the 200d). Conviction requires the news to
agree with the direction.

## 6. Pick ONE and defend it on every layer

Highest conviction = the only name clearing gate + volume floor + trend
posture + verified catalyst simultaneously. Give ref price, stop (1 ATR but
note the real stop is the post-news trigger low), breakeven trigger,
hold horizon, and a size instruction that is risk-normalised, not
share-normalised, when ATR% is high.

Always include an explicit DO NOT BUY list with the reason per name — the
backtest losers and the gate failures are as valuable as the pick.

## 7. Close with the sleeve caveat

The user's dividend DRIP sleeve is a separate book. Any momentum/news pick
must be labelled as NOT part of it. Do not log to news_trade_log.json
without asking; report it as unlogged and offer.
