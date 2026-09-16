# Crypto Sentiment Aggregator Skill

**Status:** ⏸️ STRUCTURE READY - NEEDS IMPLEMENTATION

**Priority:** MEDIUM (Efficiency)  
**Build Time:** 3h

## Purpose
Aggregate crypto sentiment across multiple sources including news, Twitter, Reddit, and Fear & Greed Index.

## Features
- Integration with Collection Sentinel (CoinDesk, Cointelegraph)
- Twitter sentiment (CT influencers)
- Reddit r/CryptoCurrency pulse
- Fear & Greed Index tracking
- Composite sentiment score (-1 to +1)
- Sentiment shift alerts

## Current Implementation
Structure created at: `~/.hermes/skills/crypto-sentiment-aggregator/`

Files:
- `skill.yaml` - Skill manifest
- `crypto_sentiment_aggregator.py` - Script stub (needs API integration)

## TODO
1. Connect to local news_db.sqlite (Collection Sentinel)
2. Set up Twitter API for influencer tracking
3. Implement Reddit scraping/parsing
4. Integrate Fear & Greed Index API
5. Create composite scoring algorithm

## Dependencies
- nltk (for sentiment analysis)
- pandas
- requests