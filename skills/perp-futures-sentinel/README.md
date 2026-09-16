# Perp Futures Sentinel Skill

**Status:** ⏸️ STRUCTURE READY - NEEDS IMPLEMENTATION

**Priority:** HIGH (Revenue-Impacting)  
**Build Time:** 4h

## Purpose
Real-time perpetual futures sentiment monitoring for funding rates, open interest, and liquidation levels.

## Features
- Funding rate tracking (all major exchanges)
- Open interest changes (>20% spike = alert)
- Long/short ratio extremes
- Liquidation heatmaps
- Basis tracking (futures vs spot premium)
- Auto-alerts for crowded trades

## Current Implementation
Structure created at: `~/.hermes/skills/perp-futures-sentinel/`

Files:
- `skill.yaml` - Skill manifest
- `perp_futures_sentinel.py` - Script stub (needs API integration)

## TODO
1. Get exchange API keys (Binance, Bybit, OKX)
2. Implement funding rate tracking
3. Set up open interest monitoring
4. Create liquidation heatmap
5. Configure alert thresholds

## API Keys Needed
- Binance Futures API
- Bybit API
- OKX API