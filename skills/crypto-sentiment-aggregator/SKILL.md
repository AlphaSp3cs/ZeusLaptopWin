---
name: crypto-sentiment-aggregator
description: "Use to aggregate crypto sentiment across news, Twitter/CT, Reddit, and Fear & Greed into one composite score (-1 fear to +1 greed). Flags sentiment shifts."
user-invocable: true
metadata:
  version: "1.0"
  author: "OuroTaurus"
  tags: ["crypto", "sentiment", "fear-greed", "aggregator"]
---

# Crypto Sentiment Aggregator

Blends your Collection Sentinel news feed, CT/Reddit pulse, and the Fear & Greed Index
into a composite -1..+1 score.

> **STATUS: LIVE but 20% COVERAGE (audited & repaired 2026-08-08).**
> Only the Fear & Greed feed is implemented. `news`, `twitter`, and `reddit` are `pass`
> stubs returning `None` — that is 80% of the intended weight missing.
> Two bugs were fixed here; both were *fabricating a plausible value instead of
> admitting missing data*:
>   1. It checked `data['status']` on the alternative.me API, which has **no such key** —
>      so every run since creation raised `KeyError`, got swallowed, and returned a
>      hardcoded `0.5` "neutral". A dead feed was reporting calm markets.
>   2. The composite multiplied `None` stubs by weights (`TypeError`), and would
>      otherwise have presented a 20%-coverage number as full confidence.
> Now: failures return `None`, the composite renormalises over available inputs only,
> and it logs coverage + a LOW CONFIDENCE warning under 60%.
> **Do not size a position off a sub-60% coverage reading.** See `signal-provenance-audit`.

## Run it
```bash
cd ~/.hermes/skills/crypto-sentiment-aggregator
python crypto_sentiment_aggregator.py hourly
python crypto_sentiment_aggregator.py report
```
## Notes
- No API key required for base feeds; CT/Reddit may need keys for full coverage.
- Log: `crypto_sentiment_aggregator.log`.
- Part of OuroTaurus gap-closure (Gap 10).
