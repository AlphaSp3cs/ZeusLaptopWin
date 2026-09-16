# Gmail Signal Auto Parser Skill

**Status:** ⏸️ STRUCTURE READY - NEEDS IMPLEMENTATION

**Priority:** MEDIUM (Efficiency)  
**Build Time:** 3h

## Purpose
Automatic parsing of Gmail signals using NLP, extracting trade recommendations and pushing to Zeus.

## Features
- Automated Gmail searches (hourly)
- NLP parsing of trade recommendations
- Extract: ticker, direction, entry, stop, targets
- Confidence scoring based on sender reputation
- Auto-push to Zeus signal queue
- Duplicate detection

## Current Implementation
Structure created at: `~/.hermes/skills/gmail-signal-auto-parser/`

Files:
- `skill.yaml` - Skill manifest
- `gmail_signal_parser.py` - Script stub (needs OAuth setup)

## TODO
1. Set up Gmail API OAuth credentials
2. Implement OAuth authentication flow
3. Create NLP signal parser (spaCy)
4. Build sender reputation system
5. Test with sample Gmail signals

## Dependencies
- google-api-python-client
- google-auth-oauthlib
- spacy

## OAuth Setup
1. Go to https://console.cloud.google.com
2. Create new project
3. Enable Gmail API
4. Create OAuth 2.0 credentials
5. Download credentials.json to skill directory