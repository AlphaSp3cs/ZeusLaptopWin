# Trading Risk Dashboard Skill

**Status:** ⏸️ STRUCTURE READY - NEEDS IMPLEMENTATION

**Priority:** HIGH (Risk Management)  
**Build Time:** 4h

## Purpose
Real-time portfolio risk monitoring including exposure, correlation, VaR, and drawdown tracking.

## Features
- Total portfolio exposure (% deployed)
- Position-level stop calculations
- Correlation matrix (BTC/ETH/altcoin)
- VaR calculation (95% confidence, 1-day)
- Drawdown tracker (max -8% rule enforcement)
- Risk odometer (Green/Yellow/Red zones)
- Auto-alerts for correlation spikes

## Current Implementation
Structure created at: `~/.hermes/skills/trading-risk-dashboard/`

Files:
- `skill.yaml` - Skill manifest
- `trading_risk_dashboard.py` - Script stub (needs implementation)

## TODO
1. Connect to positions database
2. Implement correlation matrix calculation
3. Create VaR calculation (scipy)
4. Set up drawdown tracking
5. Build risk zone logic
6. Create dashboard visualization

## Dependencies
- numpy
- pandas
- scipy (for VaR)