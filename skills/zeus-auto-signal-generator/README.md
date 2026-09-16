# Zeus Auto Signal Generator Skill

**Status:** ⏸️ STRUCTURE READY - NEEDS IMPLEMENTATION

**Priority:** CRITICAL (Execution Automation)  
**Build Time:** 3h

## Purpose
Automatic signal generation from market scans and analysis, directly populating the Zeus signal queue.

## Features
- Parse market scan reports automatically
- Auto-generate signals (ticker, direction, entry, stop, targets)
- Confidence scoring (sentiment + technicals + on-chain)
- Position sizing calculator (Kelly criterion)
- Risk/reward filtering (min 2:1 R/R)
- Direct signal_queue.db insertion

## Current Implementation
Structure created at: `~/.hermes/skills/zeus-auto-signal-generator/`

Files:
- `skill.yaml` - Skill manifest
- `zeus_auto_generator.py` - Script stub (needs NLP implementation)

## TODO
1. Implement markdown report parser
2. Set up NLP for signal extraction (spaCy)
3. Create confidence scoring algorithm
4. Implement Kelly criterion calculator
5. Test with sample market scan reports

## Dependencies
- spacy (for NLP parsing)
- pandas
- numpy