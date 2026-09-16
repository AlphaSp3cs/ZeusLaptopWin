# On-Chain Intelligence Skill

**Status:** ⏸️ STRUCTURE READY - NEEDS IMPLEMENTATION

**Priority:** HIGH (Revenue-Impacting)  
**Build Time:** 6h

## Purpose
Direct on-chain data aggregation from Glassnode and other sources for whale tracking, exchange flows, and sentiment indicators.

## Features
- Glassnode API integration (free tier)
- Exchange netflow tracking (inflows/outflows)
- Whale wallet watching (top 100 addresses)
- Stablecoin supply ratio monitoring
- MVRV Z-Score and NUPL calculation
- Auto-alerts for whale movements

## Current Implementation
Structure created at: `~/.hermes/skills/on-chain-intelligence/`

Files:
- `skill.yaml` - Skill manifest
- `on_chain_intelligence.py` - Script stub (needs API integration)

## TODO
1. Get Glassnode API key (free tier)
2. Implement exchange flow tracking
3. Set up whale wallet monitoring
4. Configure alert thresholds
5. Test with historical data

## API Keys Needed
- Glassnode API (https://glassnode.com)
- Etherscan API (https://etherscan.io)