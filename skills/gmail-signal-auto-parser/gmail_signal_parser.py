#!/usr/bin/env python3
"""
Gmail Signal Auto Parser Skill
NLP parsing of Gmail signals, auto-push to Zeus queue.

Priority: MEDIUM (Efficiency)
Build Time: 3h
"""

import sqlite3
from pathlib import Path
from datetime import datetime

# Configuration
SKILL_DIR = Path(__file__).parent
DB_PATH = SKILL_DIR / "parsed_signals.db"
LOG_PATH = SKILL_DIR / "gmail_parser.log"

try:
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build
    GOOGLE_API_AVAILABLE = True
except ImportError:
    GOOGLE_API_AVAILABLE = False
    print("Warning: Google API libraries not installed")

try:
    import spacy
    NLP_AVAILABLE = True
except ImportError:
    NLP_AVAILABLE = False
    print("Warning: spaCy not installed, NLP parsing disabled")

# Gmail search queries
SIGNAL_QUERIES = [
    "from:trading-signals subject:(buy OR sell OR long OR short)",
    "from:alerts subject:(entry OR target OR stop)",
]

def init_database():
    """Initialize parsed signals database."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Parsed signals table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS parsed_signals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            email_id TEXT,
            sender TEXT,
            ticker TEXT NOT NULL,
            direction TEXT,
            entry_price REAL,
            stop_loss REAL,
            targets TEXT,
            confidence_score REAL,
            sent_to_zeus BOOLEAN DEFAULT FALSE,
            parsed_at DATETIME
        )
    """)
    
    # Sender reputation table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sender_reputation (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT NOT NULL UNIQUE,
            total_signals INTEGER DEFAULT 0,
            accurate_signals INTEGER DEFAULT 0,
            reputation_score REAL DEFAULT 0.5
        )
    """)
    
    conn.commit()
    conn.close()
    log("Database initialized")

def log(message):
    """Log a message."""
    with open(LOG_PATH, "a") as f:
        f.write(f"[{datetime.now()}] {message}\n")

def authenticate_gmail():
    """Authenticate with Gmail API."""
    if not GOOGLE_API_AVAILABLE:
        log("Gmail API not available")
        return None
    
    # TODO: Implement OAuth flow
    creds = None
    # Load from token.json if exists
    # If not, run flow
    
    return creds

def search_gmail(query, max_results=10):
    """Search Gmail for signals."""
    log(f"Searching Gmail: {query}")
    # TODO: Use Gmail API to search
    # Return list of email IDs and snippets
    return []

def parse_signal_nlp(email_body):
    """Parse signal using NLP."""
    if not NLP_AVAILABLE:
        return parse_signal_regex(email_body)
    
    # Load NLP model
    nlp = spacy.load("en_core_web_sm")
    doc = nlp(email_body)
    
    # Extract entities
    signal = {
        'ticker': None,
        'direction': None,
        'entry': None,
        'stop': None,
        'targets': []
    }
    
    # TODO: Implement NLP extraction
    # Look for: TICKER patterns, price patterns, directional keywords
    
    return signal

def parse_signal_regex(email_body):
    """Parse signal using regex as fallback."""
    import re
# OuroTaurus secrets bootstrap (loads ~/.hermes/secure/.env; no secrets printed)
sys.path.insert(0, os.path.dirname(__file__))
import _ourotaurus_secrets  # noqa: F401
    
    signal = {
        'ticker': None,
        'direction': None,
        'entry': None,
        'stop': None,
        'targets': []
    }
    
    # Extract ticker (e.g., BTC, ETH, @BTCUSD)
    ticker_match = re.search(r'(?:@|\#)?([A-Z]{3,5})(?:USD|USDT)?', email_body)
    if ticker_match:
        signal['ticker'] = ticker_match.group(1)
    
    # Extract direction
    if any(word in email_body.lower() for word in ['buy', 'long', 'bullish']):
        signal['direction'] = 'long'
    elif any(word in email_body.lower() for word in ['sell', 'short', 'bearish']):
        signal['direction'] = 'short'
    
    # Extract entry price
    entry_match = re.search(r'(?:entry|buy|@)\s*[:\$]?\s*(\d{3,}(?:\.\d+)?)', email_body, re.IGNORECASE)
    if entry_match:
        signal['entry'] = float(entry_match.group(1))
    
    # Extract stop loss
    stop_match = re.search(r'(?:stop|sl)\s*[:\$]?\s*(\d{3,}(?:\.\d+)?)', email_body, re.IGNORECASE)
    if stop_match:
        signal['stop'] = float(stop_match.group(1))
    
    # Extract targets
    target_matches = re.findall(r'(?:target|tp)\s*\d*\s*[:\$]?\s*(\d{3,}(?:\.\d+)?)', email_body, re.IGNORECASE)
    signal['targets'] = [float(t) for t in target_matches]
    
    return signal

def calculate_sender_confidence(sender_email):
    """Calculate confidence based on sender reputation."""
    # TODO: Query sender_reputation table
    # Return reputation score as confidence
    return 75.0  # Default

def push_to_zeus(signal):
    """Push parsed signal to Zeus queue."""
    log(f"Pushing signal to Zeus: {signal['ticker']}")
    
    # Connect to Zeus queue
    zeus_db = Path.home() / ".hermes" / "zeus" / "signal_queue.db"
    if not zeus_db.exists():
        log("Zeus queue not found")
        return False
    
    conn = sqlite3.connect(zeus_db)
    cursor = conn.cursor()
    
    # Insert signal
    cursor.execute("""
        INSERT INTO signals (
            timestamp, ticker, direction, entry_price,
            stop_loss, target_1, target_2, target_3,
            confidence, source
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        datetime.now(), signal['ticker'], signal['direction'],
        signal['entry'], signal['stop'],
        signal['targets'][0] if len(signal['targets']) > 0 else None,
        signal['targets'][1] if len(signal['targets']) > 1 else None,
        signal['targets'][2] if len(signal['targets']) > 2 else None,
        signal['confidence'], 'gmail'
    ))
    
    conn.commit()
    conn.close()
    
    log(f"Signal pushed to Zeus: {signal['ticker']}")
    return True

def run_gmail_scan():
    """Run hourly Gmail signal scan."""
    log("Starting Gmail signal scan...")
    
    creds = authenticate_gmail()
    if not creds:
        log("Authentication failed, skipping scan")
        return
    
    for query in SIGNAL_QUERIES:
        emails = search_gmail(query)
        
        for email in emails:
            # Parse signal
            signal = parse_signal_nlp(email['body'])
            
            if signal['ticker'] and signal['direction']:
                # Add confidence score
                signal['confidence'] = calculate_sender_confidence(email['sender'])
                
                # Push to Zeus
                push_to_zeus(signal)
                
                # Log parsed signal
                log_parsed_signal(email, signal)
    
    log("Gmail scan complete")

def log_parsed_signal(email, signal):
    """Log parsed signal to database."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("""
        INSERT INTO parsed_signals (
            email_id, sender, ticker, direction, entry_price,
            stop_loss, targets, confidence_score, sent_to_zeus, parsed_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        email['id'], email['sender'], signal['ticker'], signal['direction'],
        signal['entry'], signal['stop'], str(signal['targets']),
        signal['confidence'], True, datetime.now()
    ))
    
    conn.commit()
    conn.close()

if __name__ == "__main__":
    init_database()
    run_gmail_scan()
