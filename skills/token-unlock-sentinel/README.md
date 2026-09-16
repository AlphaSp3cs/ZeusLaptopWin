# Token Unlock Sentinel Skill

**Status:** ⏸️ STRUCTURE READY - NEEDS IMPLEMENTATION

**Priority:** MEDIUM (Risk Prevention)  
**Build Time:** 2h

## Purpose
Token unlock calendar and supply shock warnings from TokenUnlocks.app.

## Features
- TokenUnlocks.app API integration
- 7-day/30-day/90-day unlock calendar
- Supply shock detection (>5% of circulating)
- Auto-alerts for upcoming unlocks
- Historical unlock performance tracking
- Token-specific unlock profiles

## Current Implementation
Structure created at: `~/.hermes/skills/token-unlock-sentinel/`

Files:
- `skill.yaml` - Skill manifest
- `token_unlock_sentinel.py` - Script stub (needs API integration)

## TODO
1. Set up TokenUnlocks.app data source (API or scraping)
2. Create unlock calendar database
3. Implement supply shock detection
4. Build alert system
5. Track historical unlock performance