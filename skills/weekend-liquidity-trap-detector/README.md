# Weekend Liquidity Trap Detector Skill

**Status:** ⏸️ STRUCTURE READY - NEEDS IMPLEMENTATION

**Priority:** MEDIUM-HIGH (Risk Prevention)  
**Build Time:** 2h

## Purpose
Weekend liquidity analysis to identify pump/dump traps and low-volume manipulation patterns.

## Features
- Volume analysis (weekend vs weekday avg)
- Bid-ask spread monitoring
- Order book depth tracking
- Pump detection algorithm (>5% in <10min on low vol)
- Auto-warning system with confidence scoring
- Historical weekend pattern database

## Current Implementation
Structure created at: `~/.hermes/skills/weekend-liquidity-trap-detector/`

Files:
- `skill.yaml` - Skill manifest
- `weekend_liquidity_detector.py` - Script stub (needs implementation)

## TODO
1. Implement volume comparison algorithm
2. Set up spread monitoring
3. Create pump detection logic
4. Build confidence scoring system
5. Generate weekend outlook reports