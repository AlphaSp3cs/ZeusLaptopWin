---
name: zeus-auto-signal-generator
description: "Use to auto-generate Zeus trade signals from market-scan reports: parses {ticker, direction, entry, stop, targets}, scores confidence, inserts into signal_queue.db. Closes the execution-automation gap."
user-invocable: true
metadata:
  version: "1.0"
  author: "OuroTaurus"
  tags: ["crypto", "signals", "zeus", "execution"]
---

# Zeus Auto Signal Generator

Parses market-scan markdown into structured signals, applies confidence scoring
(sentiment + technicals), enforces min 2:1 R/R and 1% risk sizing, and writes directly
to `signal_queue.db`. Closes Gap 6 (manual signal entry).

## Run it
```bash
cd ~/.hermes/skills/zeus-auto-signal-generator
python zeus_auto_generator.py parse <path-to-scan-report.md>   # emit signals
python zeus_auto_generator.py quality                           # signal quality report
```
## Notes
- Expects the standard scan-report format. If parsing a new report shape, validate output before trusting it.
- Writes to Zeus `signal_queue.db`.
- Part of OuroTaurus gap-closure (Gap 6).
