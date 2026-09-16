---
name: crypto-bottom-universe-rescreen
description: Use to source crypto DCA candidates from the full universe.
---

# Crypto Bottom-Universe Rescreen (candidate sourcing)

Class of request: "is anything oversold in the ENTIRE crypto universe?" / "find me
DCA candidates beyond the weekend scan" / "what's at a real bottom right now?"

## The core misconception this fixes

`scan.py crypto` (Cerebro weekend mode) only runs a **liquid-movers filter**:
min $50M 24h volume AND min 2% 24h move, top ~25. It returns ~9 names — SOL,
NEAR, BONK, etc. — NOT the universe. Saying "the scan shows nothing to buy" is
NOT the same as "nothing in the universe is oversold." If the user asks whether
anything oversold exists anywhere, you MUST run a full-universe rescreen. That
is this skill.

The rescreen is the **upstream half** of the DCA workflow: it produces the
candidate list. The ladder/tranche mechanics live in `crypto-dca-ladder-reminders`
which is user-owned (recommend `hermes curator adopt` to extend it). This skill
ends where that one begins.

## Base-rate rule (load-bearing — from the user's measured study)

- ONLY the `<= -90% from ATH` bucket has a positive forward median: 12m +44.6%
  (65% win), 24m +109% (72% win). This is the ONLY bucket worth accumulating.
- The `-70% .. -25%` band is a capital incinerator (12m median -40% to -57%).
- Exclude anything reading `-100% from ATH` — that's a dead/illiquid token or a
  busted ATH data point, not a real bottom.

## Working method (validated 2026-08-08)

1. Pull CoinGecko `/coins/markets` top-500 (`vs_currency=usd`, pages of 250).
   This gives `ath_change_percentage` directly — no need to fetch ATH history.
2. Filter `ath_change_percentage <= -90` (deep-from-ATH bucket).
3. Keep only liquid names: `total_volume >= $5M` (so a ladder is actually tradeable).
4. For surviving symbols, fetch Binance `fetch_ohlcv(pair, "1h", limit=120)`
   via ccxt and compute `rsi14`. Mark `RSI < 35` as oversold.
5. Report the liquid far-from-ATH survivors sorted by depth, flag oversold ones.

Script: `scripts/crypto_bottom_rescreen_live.py` (run: `python3 crypto_bottom_rescreen_live.py`).
Requires `ccxt` + `requests` (both present on this box, no install needed).
A checked-in copy of the working script is in this skill's scripts/ dir — copy it to ~ and run.

## Pitfalls

- **CoinGecko rate limit (429).** Sleep ~1.5s between the two top-500 pages or
  the second page 429s and you silently get a half-universe. The script sleeps.
- **`-100% ATH` is a red flag**, not a bargain — exclude before RSI (saves an
  API call and a bad candidate). SUN read -100.0% on 2026-08-08; dropped.
- **yfinance `-USD` feeds for renamed tokens are squatted** (read ~$0.0001 in
  2026). Use CoinGecko + Binance directly; do NOT cross-check renamed tokens
  against yfinance here.
- **The weekend scan and this rescreen answer different questions.** Don't
  substitute one for the other. Use the rescreen to BUILD the candidate queue;
  use the ladder skill to DEPLOY into it.

## 2026-08-08 measured snapshot (for sanity-checking future runs)

- top-500: 197 coins at `<= -90%` from ATH; 80 liquid enough to ladder.
- 7 oversold (RSI < 35): SUN(-100, exc), KMNO(-92.6, RSI26.8, still falling),
  COMP(-98, RSI26.8, thin), JTO(-91.9, RSI26.9), ENA(-94, RSI32.9),
  IOTA(-99.4, RSI33.3), ALGO(-97.6, RSI33.3).
- Quality subset (real projects + real volume + oversold): **ALGO, IOTA, JTO, ENA**.
  These became the live ladder universe in `crypto-dca-ladder-reminders`.
