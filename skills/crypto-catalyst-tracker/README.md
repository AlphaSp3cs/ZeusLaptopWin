# Crypto Catalyst Tracker Skill

**Status:** ⏸️ STRUCTURE READY - NEEDS IMPLEMENTATION

**Priority:** MEDIUM (Opportunity Capture)  
**Build Time:** 2h

## Purpose
Track upcoming crypto catalysts including upgrades, hard forks, governance votes, and major events.

## Features
- Events database (upgrades, hard forks, unlocks, votes)
- Timeline view with countdown alerts
- Catalyst scoring (High/Med/Low impact)
- Pre-event positioning reminders
- Historical catalyst performance
- Multi-chain event tracking

## Current Implementation
Structure created at: `~/.hermes/skills/crypto-catalyst-tracker/`

Files:
- `skill.yaml` - Skill manifest
- `crypto_catalyst_tracker.py` - Script stub (needs data integration)

## TODO
1. Integrate CoinMarketCal API/data
2. Set up CoinGecko events API
3. Create catalyst scoring algorithm
4. Implement countdown alert system
5. Build weekly calendar report

## Dependencies
- icalendar (for calendar integration)
- pandas
- requests