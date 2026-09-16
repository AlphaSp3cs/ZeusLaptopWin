# Asia Session Sentinel Skill

**Status:** ⏸️ STRUCTURE READY - NEEDS IMPLEMENTATION

**Priority:** MEDIUM (Opportunity Capture)  
**Build Time:** 3h

## Purpose
Automated monitoring of Asia trading session (10pm-4am EST) for volume spikes and regional news.

## Features
- 10pm-4am EST automated watch
- BTC/ETH volume spikes (>50% above avg)
- Exchange-specific flows (Binance vs OKX vs Huobi)
- China/HK/KR news sentiment parsing
- Auto-alerts for Asia-driven moves
- Dip entry signal generation

## Current Implementation
Structure created at: `~/.hermes/skills/asia-session-sentinel/`

Files:
- `skill.yaml` - Skill manifest
- `asia_session_sentinel.py` - Script stub (needs implementation)

## TODO
1. Set up Asia session hour tracking
2. Implement volume spike detection
3. Monitor Asia-centric exchanges
4. Set up regional news parsing
5. Create dip signal generator