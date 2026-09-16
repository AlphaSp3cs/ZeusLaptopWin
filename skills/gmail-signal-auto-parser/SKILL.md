---
name: gmail-signal-auto-parser
description: "Use to auto-parse Gmail trading signals (Buy/Sell, entry, stop) via NLP and push them to the Zeus queue. Removes manual copy-paste and typos."
user-invocable: true
metadata:
  version: "1.0"
  author: "OuroTaurus"
  tags: ["gmail", "signals", "zeus", "nlp"]
---

# Gmail Signal Auto Parser

Searches configured SIGNAL_QUERIES in Gmail, NLP-parses "Buy BTC at $63K stop $61.5K"
into {ticker, direction, entry, stop}, scores by sender reputation, and pushes to Zeus.

## Run it
```bash
cd ~/.hermes/skills/gmail-signal-auto-parser
python gmail_signal_parser.py
```
## Notes
- Requires Gmail API credentials in `.env` (google-workspace auth).
- Log: `gmail_signal_parser.log`.
- Part of OuroTaurus gap-closure (Gap 9).
