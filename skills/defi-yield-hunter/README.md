# DeFi Yield Hunter Skill

**Status:** ⏸️ STRUCTURE READY - NEEDS IMPLEMENTATION

**Priority:** HIGH (Revenue-Impacting)  
**Build Time:** 4h

## Purpose
DeFi TVL and yield tracker using DeFiLlama API for identifying yield opportunities and governance events.

## Features
- DeFiLlama API integration (all chains)
- TVL change alerts (>10% weekly shift)
- Yield farming opportunities (APY >20%)
- Governance token alerts (upcoming votes)
- Token unlock calendar integration
- Auto-ranking of top yield opportunities

## Current Implementation
Structure created at: `~/.hermes/skills/defi-yield-hunter/`

Files:
- `skill.yaml` - Skill manifest
- `defi_yield_hunter.py` - Script stub (needs API integration)

## TODO
1. Implement DeFiLlama API calls
2. Set up TVL tracking database
3. Create yield ranking algorithm
4. Configure alert thresholds
5. Build weekly report generator