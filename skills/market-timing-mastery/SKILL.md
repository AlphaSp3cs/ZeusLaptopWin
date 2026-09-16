---
name: market-timing-mastery
description: Use when running any market scan, building a buy plan, or answering "when is the right time to buy X". Master timing windows, market structure, and risk rules across forex, commodities, indices, crypto (nightshift) and ETFs, stocks, bonds, futures, options (dayshift).
---

# Market Timing Mastery — Multi-Asset Buy Timing & Structure

A master trader knows two things for every asset: (1) the TIME WINDOW when price is
most likely to be bought/acquired well, and (2) the STRUCTURE that confirms a real
entry vs. a trap. This skill is the standing playbook. Apply it on every scan for
Victor's dividend-compounding, buy-and-hold, add-on-dips mandate.

## Standing rules (from .hermes.md)
- Goal is long-horizon compounding for monthly income (DRIP, buy-and-hold, add on dips), NOT trading.
- Every scan must integrate blogwatcher_integration.py RSS sentiment (regime shift risk). Note it only covers BTC/ETH/SOL — for other assets say per-symbol layer is unavailable rather than implying coverage.
- Backtest validation required before trade tickets: a gate GO proves risk mechanics, not edge. PF < 1.0 = do not trade. Positive/negative expectancy split, explicit DO NOT TRADE list, kill list carried across runs.
- State instrument + basis; never conflate spot vs futures (Yahoo XAUUSD=X/WTICOUSD=X/USOIL 404).

## SHIFT MAP
- NIGHTSHIFT (market closed, ~US evening to 8am EST next day): priority = FOREX, COMMODITIES (gold/oil), INDICES (futures), CRYPTO.
- DAYSHIFT (US cash session): priority = ETFs, STOCKS, BONDS, FUTURES, OPTIONS and everything listed above that runs in the day.

================================================================
## 1. FOREX (nightshift core)
================================================================
Sessions (ET):
- Tokyo/Asian: 7pm–4am ET (opens 6pm Sun). Lowest vol, range-bound; JPY pairs & AUD/NZD live here.
- London/European: 3am–12pm ET. MOST active (~38% of daily volume). GBP/EUR pairs peak.
- New York: 8am–5pm ET. 2nd largest. USD pairs peak.
- Best liquidity window: London/NY overlap 8am–12pm ET (1pm–4pm UTC) — NOT a nightshift hour, so for nightshift the London open 3–6am ET and Asian range are the actionable windows.

Best DAYS: Tue–Thu (highest liquidity/vol). Avoid Mondays (settlement gaps) and Fridays afternoon (position squaring / weekend risk).

STRUCTURE (ICT / Smart Money — works best on FX & gold):
- Order Block (OB): last counter candle before a strong impulse. Bullish OB = last bearish candle before up-impulse; Bearish OB = last bullish candle before down-impulse. Price returns to OB, unfilled orders mitigate, then the move resumes.
- Fair Value Gap (FVG): imbalance left by a 3-candle move; price tends to fill it. An OB WITH an adjacent FVG is high-probability.
- Liquidity sweep: price hunts stops above equal highs / below equal lows, then reverses. BUY after a sweep of prior lows into a bullish OB + FVG + market-structure shift (MSS) on lower TF (5m/15m).
- Killzones (NY time): London KZ 2–5am ET; NY AM KZ 8–11am ET; NY PM KZ 2–3pm ET (Silver Bullet 10–11am & 2–3pm). For nightshift: London KZ 2–5am ET and Asian range are the windows.
- Higher TF for bias (daily/4h OB), entry TF 15m/5m.
- Whole numbers (1.2000) and daily pivots often coincide with OBs.

NEWS: NFP (1st Fri 8:30am ET), FOMC, CPI are high-impact. Most traders WAIT 15–30 min after red-flag news before trading. Never hold into NFP blindly.

WHEN TO BUY (nightshift): after a London/NY session sweep of liquidity lows → retrace into a bullish OB+FVG in the London KZ (2–5am ET) or on Asian-range reversals; confirm with MSS.

================================================================
## 2. COMMODITIES — GOLD (XAU/USD) & OIL (WTI)
================================================================
GOLD:
- 24h CME Globex with daily 5pm–6pm ET break (Sunday 6pm ET open).
- Most active: London open (3am ET) + NY session (8am–1pm ET). Quietest Asian hours.
- Respects OB/FVG + liquidity-sweep mechanics like FX. Safe-haven flows on risk-off.
- Seasonality: historically strong Jan & Aug; soft in Mar/Sept/Oct.
- Nightshift buy: sweep of prior lows into bullish OB during London KZ, OR on risk-off spike that reclaims an OB.

OIL (WTI Crude):
- CME Globex 6pm–5pm ET with 5–6pm break. Peak liquidity ~NY open 9:30am + London.
- API report Tue 4:30pm ET, EIA inventory Wed 10:30am ET — big vol spikes, trade AFTER the print, not into it.
- Cycle: tends to trend with global growth / USD inverse.
- Nightshift buy: London-session reversal off a swept low into OB; avoid holding into Wed EIA.

Note: Yahoo tickers XAUUSD=X / WTICOUSD=X / USOIL 404 — use futures basis (GC=F, CL=F) or state spot vs futures explicitly.

================================================================
## 3. INDICES — S&P500 (ES), Nasdaq (NQ), Dow (YM) FUTURES
================================================================
- CME Globex: Sunday 6pm ET – Friday 4pm ET, daily halt 4–5pm ET. (24/7 gold/oil expansion in 2025 does not yet cover index futures.)
- Best intraday windows:
  - US open 9:30–11:30am ET (prime time, biggest range; ORB here).
  - Afternoon 2–4pm ET (renewed vol, trend continuation or fade).
  - Overnight 6pm–8:30am ET: lighter vol, Asian (7pm–3am) + European open (3–6am). Lower liquidity → conservative size, wider stop.
- Cleanest OB/FVG structure of any asset (tight impulses). Daily/4h OB for bias, 15m/5m entry.
- Nightshift buy: European open 3–6am ET sweep into bullish OB; or gap-fill setups off the Asian range.

================================================================
## 4. CRYPTO — BTC / ETH / SOL (24/7, nightshift-friendly)
================================================================
- 24/7 markets; best global liquidity = London/NY overlap 2:30–4:30pm UTC (10:30am–12:30pm ET) and mid-week Tue–Thu.
- Day-of-week edge (close-to-close): biggest positive moves Fri close→Mon open, Mon close→Tue open, Tue close→Wed open. Weekend often grinds up.
- 4-YEAR HALVING CYCLE: tops ~18 months post-halving, bottoms ~24–28 months post-halving. Last cycle top was Oct 2025 (~$126k); drawdown in progress. Base-case bottom zone discussed $40k–62k, window May–Dec 2026. Compressing amplitude — old "75–85% drop" floor is obsolete.
- Buy strategy for compounding: DCA through expected bottom window (2026) to remove timing risk; add on dips into HTF support / prior range highs turned support.
- Per-symbol RSS sentiment layer = BTC/ETH/SOL only (blogwatcher). For other coins state layer unavailable.
- Structure: same OB/FVG/liquidity-sweep logic; higher vol → wider stops, smaller size.

================================================================
## 5. ETFs & STOCKS (dayshift)
================================================================
Best intraday windows (ET):
- Open 9:30–10:30am — most vol/range (processes overnight news, gaps). Opening Range Breakout (ORB) = enter above/below first 5–30min range.
- Midday 11:30am–1:30pm — lull, range/mean-reversion.
- Close 3–4pm — vol returns, institutional rebalance.
- Pre-market 8–9:30am & after-hours 4–8pm: catalyst/earnings, wide spreads, limit orders only.
- Best DAY: Tuesday highest avg return historically; Friday/Monday lowest.
- Seasonality: "Sell in May" weak summer; strong Nov–Apr; Santa Claus rally late Dec; early-month & pre-holiday (Thanksgiving, long weekend) bullish bias.

ETFs for the dividend-compounding mandate (vetted, low cost):
- Core: VOO (S&P500, 0.03%, ~15% 10y), QQQ (Nasdaq100, 0.18%, ~21% 10y), VXUS (intl, 0.05%), VT (total world, 0.06%).
- Income/dividend: SCHD (US dividend equity, quality screen), VYM (high div yield ~2.3%), VGSH (short Treasury, dur<2y, rate-shock resistant).
- International value tilt: DFIV.
- Buy-the-dip rule: add to core ETFs on >5–10% drawdowns from 52w high into HTF support; DCA, never all-at-once.

STOCKS: buy fundamentally sound, dividend-growing names on weakness; watch ORB + earnings dates (avoid buying calls/longs blindly into earnings IV crush — see Options).

================================================================
## 6. BONDS (dayshift / futures)
================================================================
- Treasury futures (ZN 10y, ZB 30y, ZT 2y, ZF 5y): CME, ~8pm–5pm ET with breaks. Most active at US cash open & FOMC.
- Yield curve is the master signal:
  - NORMAL (up-sloping): growth/expansion → own longer duration for price gains.
  - INVERTED (2y > 10y, or 3m > 10y): recession warning, leads by 6–22 months. Historically ~9 of 10 inversions preceded recession.
  - FLAT: transition/uncertainty.
- Strategy: inverted curve → favor SHORT duration (VGSH) or roll into quality; normal curve → can extend duration for capital gains ("ride the curve").
- Duration = sensitivity to rates (modified duration ≈ % price change per 1% yield move). Higher duration = higher rate risk.
- Bonds rally when yields fall (prices inverse to yields).

================================================================
## 7. FUTURES & OPTIONS (dayshift)
================================================================
FUTURES:
- 24/5 CME; best windows = US open 8:30–11:30am ET, afternoon 2–4pm, overnight Asian/European (lighter).
- Position sizing on futures uses $/point (ES=$50/pt, NQ=$20/pt, etc.). 1% risk rule: size = (1% acct) / (stop pts × $/pt).
- Margin is leverage — respect it.

OPTIONS:
- Greeks to read every position:
  - Delta: directional exposure (calls +, puts -). ~0.50 ATM.
  - Gamma: delta acceleration; high near ATM, blows up near expiry (0DTE risk).
  - Theta: time decay; buyers lose daily, sellers collect. Theta accelerates last 30 days.
  - Vega: sensitivity to IV; long vega profits if IV rises.
  - Rho: rate sensitivity (minor).
- IV CRUSH: IV spikes into earnings/FOMC then collapses after. BUYING options into events is often a loser even if direction right (IV drop eats premium). SELLING premium (credit spreads) benefits from crush when confident in a "non-event".
- IV Rank: >50% = sell vol (elevated); <20% = buy vol (cheap). Watch VIX: 20s–30s = sellers active.
- 0DTE SPX: high gamma, fast, expert-only.
- For the dividend mandate: cash-secured puts to ACCUMULATE at lower prices (get paid to wait), covered calls to milk income on held stock. Avoid speculative long premium into known events.

================================================================
## 8. RISK MANAGEMENT (non-negotiable, all assets)
================================================================
- 1% RULE: risk ≤1% of account equity per trade (≤0.5% while unproven). Max loss is fixed FIRST; stop placement drives position size, never the reverse.
- R-MULTIPLE: express every outcome in R. +2R win, -1R loss. Track win-rate × avg R to confirm positive expectancy (PF = (win%×avgW)/(loss%×avgL) ≥1.0 to trade).
- Always define invalidation (stop) BEFORE entry. No stop = no trade.
- Never hold a fresh position into a red-flag macro event (NFP/FOMC/CPI/EIA) without a plan; or flatten.
- Kill list: symbols that failed the gate carry forward; if the scanner re-emits one, re-check the original disqualifier before any ticket.
- Size down in low-liquidity windows (overnight, Asian, pre/after-market).

## HOW TO APPLY ON A SCAN
1. Identify shift (night vs day) → filter asset priority list above.
2. For each candidate: is it inside an actionable TIME window? Is there HTF bias (OB/FVG/support) aligning? Is RSS sentiment (where available) supportive or a regime-risk flag?
3. Gate it (run_gate / backtest). PF<1.0 → DO NOT TRADE, add to kill list.
4. For GOs: emit sequential execution doc with explicit limit prices, entry/stop/TP1/TP2, scale-out %, size from 1% rule, fill log, best-backtest-first, instrument+basis clearly stated.

## PITFALLS
- Conflating spot vs futures basis (XAUUSD=X/WTICOUSD=X/USOIL 404) — state basis.
- Buying options into earnings expecting a win — IV crush kills it.
- Trading the dead midday lull or the illiquid Asian-hour FX with day-session size.
- Ignoring the yield curve (missing recession signal) or RSS regime shift.
- Sizing off conviction instead of off the stop distance.
- Treating crypto's old 80% drawdown floor as gospel — cycle is compressing.
