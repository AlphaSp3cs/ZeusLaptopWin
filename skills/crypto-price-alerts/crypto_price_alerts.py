#!/usr/bin/env python3
"""
Crypto Price Alerts — Real-Time Price Monitoring

Features:
- Set price alerts for BTC, ETH, and major alts
- Push notifications via Telegram
- Webhook integration for Zeus auto-execution
- Historical alert tracking
- CoinGecko API integration (free tier)

Usage:
    python crypto_price_alerts.py --set-alert BTC --price 62000 --direction below
    python crypto_price_alerts.py --check
    python crypto_price_alerts.py --list-alerts
    python crypto_price_alerts.py --clear-alerts
"""

import json
import os
import sys
import time
import sqlite3
import requests
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# OuroTaurus secrets bootstrap (loads ~/.hermes/secure/.env; no secrets printed)
sys.path.insert(0, os.path.dirname(__file__))
import _ourotaurus_secrets  # noqa: F401

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(Path(__file__).parent / 'price_alerts.log')
    ]
)
logger = logging.getLogger(__name__)

# CoinGecko API (free tier: 10-30 calls/min)
COINGECKO_API = "https://api.coingecko.com/api/v3"
COINGECKO_IDS = {
    'BTC': 'bitcoin',
    'ETH': 'ethereum',
    'BNB': 'binancecoin',
    'SOL': 'solana',
    'XRP': 'ripple',
    'ADA': 'cardano',
    'DOGE': 'dogecoin',
    'AVAX': 'avalanche-2',
    'LINK': 'chainlink',
    'DOT': 'polkadot',
    'MATIC': 'matic-network',
    'UNI': 'uniswap',
    'AAVE': 'aave',
    'ZEC': 'zcash'
}

# Alert database
DB_PATH = Path(__file__).parent / 'price_alerts.db'

# Telegram bot config (optional)
TELEGRAM_ENABLED = False
TELEGRAM_BOT_TOKEN = os.getenv('HERMES_TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('HERMES_TELEGRAM_USER_ID')

if TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID:
    TELEGRAM_ENABLED = True
    logger.info("Telegram notifications enabled")
else:
    logger.warning("Telegram not configured — alerts logged only")


def init_db():
    """Initialize SQLite database for alerts"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker TEXT NOT NULL,
            direction TEXT NOT NULL,  -- 'above' or 'below'
            target_price REAL NOT NULL,
            current_price REAL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            triggered_at TIMESTAMP,
            triggered_price REAL,
            status TEXT DEFAULT 'active',  -- 'active', 'triggered', 'cancelled'
            notified INTEGER DEFAULT 0,
            webhook_url TEXT
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS price_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker TEXT NOT NULL,
            price REAL NOT NULL,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS alert_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            alert_id INTEGER,
            message TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (alert_id) REFERENCES alerts(id)
        )
    ''')
    
    conn.commit()
    conn.close()


def get_price(ticker: str) -> Optional[float]:
    """Fetch current price from CoinGecko"""
    ticker_upper = ticker.upper()
    if ticker_upper not in COINGECKO_IDS:
        logger.error(f"Unknown ticker: {ticker}")
        return None
    
    coin_id = COINGECKO_IDS[ticker_upper]
    
    try:
        response = requests.get(
            f"{COINGECKO_API}/simple/price",
            params={'ids': coin_id, 'vs_currencies': 'usd'},
            timeout=10
        )
        response.raise_for_status()
        data = response.json()
        price = data[coin_id]['usd']
        return float(price)
    except requests.exceptions.RequestException as e:
        logger.error(f"API error for {ticker}: {e}")
        return None
    except (KeyError, ValueError) as e:
        logger.error(f"Parse error for {ticker}: {e}")
        return None


def get_multiple_prices(tickers: List[str]) -> Dict[str, float]:
    """Fetch prices for multiple tickers in one API call"""
    coin_ids = []
    ticker_to_id = {}
    
    for ticker in tickers:
        ticker_upper = ticker.upper()
        if ticker_upper in COINGECKO_IDS:
            coin_ids.append(COINGECKO_IDS[ticker_upper])
            ticker_to_id[COINGECKO_IDS[ticker_upper]] = ticker_upper
    
    if not coin_ids:
        return {}
    
    try:
        response = requests.get(
            f"{COINGECKO_API}/simple/price",
            params={'ids': ','.join(coin_ids), 'vs_currencies': 'usd'},
            timeout=10
        )
        response.raise_for_status()
        data = response.json()
        
        prices = {}
        for coin_id, price_data in data.items():
            ticker = ticker_to_id.get(coin_id)
            if ticker:
                prices[ticker] = float(price_data['usd'])
        
        return prices
    except Exception as e:
        logger.error(f"Batch price fetch failed: {e}")
        return {}


def set_alert(ticker: str, direction: str, target_price: float, webhook_url: Optional[str] = None) -> int:
    """Create a new price alert"""
    ticker_upper = ticker.upper()
    direction_lower = direction.lower()
    
    if direction_lower not in ['above', 'below']:
        logger.error("Direction must be 'above' or 'below'")
        return -1
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT INTO alerts (ticker, direction, target_price, webhook_url)
        VALUES (?, ?, ?, ?)
    ''', (ticker_upper, direction_lower, target_price, webhook_url))
    
    alert_id = cursor.lastrowid
    
    # Log the alert
    cursor.execute('''
        INSERT INTO alert_log (alert_id, message)
        VALUES (?, ?)
    ''', (alert_id, f"Alert created: {ticker_upper} {direction_lower} ${target_price:,.2f}"))
    
    conn.commit()
    conn.close()
    
    logger.info(f"Alert #{alert_id} created: {ticker_upper} {direction_lower} ${target_price:,.2f}")
    return alert_id


def list_alerts() -> List[Dict]:
    """List all active alerts"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT id, ticker, direction, target_price, current_price, 
               created_at, status, webhook_url
        FROM alerts
        WHERE status = 'active'
        ORDER BY created_at DESC
    ''')
    
    alerts = []
    for row in cursor.fetchall():
        alerts.append({
            'id': row[0],
            'ticker': row[1],
            'direction': row[2],
            'target_price': row[3],
            'current_price': row[4],
            'created_at': row[5],
            'status': row[6],
            'webhook_url': row[7]
        })
    
    conn.close()
    return alerts


def cancel_alert(alert_id: int) -> bool:
    """Cancel an alert"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute('''
        UPDATE alerts SET status = 'cancelled' WHERE id = ? AND status = 'active'
    ''', (alert_id,))
    
    if cursor.rowcount > 0:
        cursor.execute('''
            INSERT INTO alert_log (alert_id, message)
            VALUES (?, ?)
        ''', (alert_id, "Alert cancelled"))
        conn.commit()
        logger.info(f"Alert #{alert_id} cancelled")
        success = True
    else:
        logger.warning(f"Alert #{alert_id} not found or already cancelled")
        success = False
    
    conn.close()
    return success


def check_alerts() -> List[Dict]:
    """Check all active alerts against current prices"""
    alerts = list_alerts()
    
    if not alerts:
        logger.info("No active alerts")
        return []
    
    # Get unique tickers
    tickers = list(set([a['ticker'] for a in alerts]))
    prices = get_multiple_prices(tickers)
    
    if not prices:
        logger.error("Failed to fetch prices")
        return []
    
    triggered = []
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    for alert in alerts:
        ticker = alert['ticker']
        if ticker not in prices:
            continue
        
        current_price = prices[ticker]
        target_price = alert['target_price']
        direction = alert['direction']
        
        # Update current price in DB
        cursor.execute('''
            UPDATE alerts SET current_price = ? WHERE id = ?
        ''', (current_price, alert['id']))
        
        # Check if triggered
        is_triggered = False
        if direction == 'above' and current_price >= target_price:
            is_triggered = True
            message = f"🚀 {ticker} hit ${current_price:,.2f} (target: ${target_price:,.2f})"
        elif direction == 'below' and current_price <= target_price:
            is_triggered = True
            message = f"📉 {ticker} dropped to ${current_price:,.2f} (target: ${target_price:,.2f})"
        
        if is_triggered:
            logger.warning(f"ALERT TRIGGERED: {message}")
            
            # Update alert status
            cursor.execute('''
                UPDATE alerts 
                SET status = 'triggered', triggered_at = ?, triggered_price = ?
                WHERE id = ?
            ''', (datetime.now().isoformat(), current_price, alert['id']))
            
            # Log trigger
            cursor.execute('''
                INSERT INTO alert_log (alert_id, message)
                VALUES (?, ?)
            ''', (alert['id'], f"TRIGGERED: {message}"))
            
            # Send notification
            send_notification(message, alert)
            
            triggered.append({
                'alert_id': alert['id'],
                'ticker': ticker,
                'direction': direction,
                'target_price': target_price,
                'triggered_price': current_price,
                'message': message
            })
    
    conn.commit()
    conn.close()
    
    if not triggered:
        logger.info(f"Checked {len(alerts)} alerts — none triggered")
    
    return triggered


def send_notification(message: str, alert: Dict):
    """Send alert notification via Telegram and/or webhook"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    full_message = f"[{timestamp}] {message}"
    
    # Telegram notification
    if TELEGRAM_ENABLED:
        try:
            url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
            data = {
                'chat_id': TELEGRAM_CHAT_ID,
                'text': full_message,
                'parse_mode': 'Markdown'
            }
            response = requests.post(url, json=data, timeout=10)
            if response.status_code == 200:
                logger.info("Telegram notification sent")
            else:
                logger.error(f"Telegram API error: {response.status_code}")
        except Exception as e:
            logger.error(f"Telegram notification failed: {e}")
    
    # Webhook notification (for Zeus integration)
    if alert.get('webhook_url'):
        try:
            webhook_data = {
                'event': 'price_alert',
                'timestamp': timestamp,
                'alert_id': alert['id'],
                'ticker': alert['ticker'],
                'direction': alert['direction'],
                'target_price': alert['target_price'],
                'triggered_price': alert.get('current_price'),
                'message': message
            }
            response = requests.post(
                alert['webhook_url'],
                json=webhook_data,
                timeout=10,
                headers={'Content-Type': 'application/json'}
            )
            if response.status_code in [200, 201]:
                logger.info(f"Webhook notification sent to {alert['webhook_url']}")
            else:
                logger.error(f"Webhook error: {response.status_code}")
        except Exception as e:
            logger.error(f"Webhook notification failed: {e}")
    
    # Always log to database
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO alert_log (alert_id, message)
        VALUES (?, ?)
    ''', (alert['id'], f"Notification sent: {full_message}"))
    conn.commit()
    conn.close()


def show_alert_history(limit: int = 20) -> List[Dict]:
    """Show recent alert history"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT id, alert_id, message, timestamp
        FROM alert_log
        ORDER BY timestamp DESC
        LIMIT ?
    ''', (limit,))
    
    history = []
    for row in cursor.fetchall():
        history.append({
            'id': row[0],
            'alert_id': row[1],
            'message': row[2],
            'timestamp': row[3]
        })
    
    conn.close()
    return history


def quick_setup_default_alerts():
    """Set up some default price alerts for common levels"""
    logger.info("Setting up default alerts...")
    
    # Get current prices
    tickers = ['BTC', 'ETH', 'SOL']
    prices = get_multiple_prices(tickers)
    
    if not prices:
        logger.error("Could not fetch prices for setup")
        return
    
    alerts_created = []
    
    for ticker, price in prices.items():
        # Set alerts at ±5%, ±10% levels
        levels = [0.90, 0.95, 1.05, 1.10]
        for level in levels:
            target = price * level
            direction = 'below' if level < 1.0 else 'above'
            alert_id = set_alert(ticker, direction, target)
            if alert_id > 0:
                alerts_created.append((ticker, direction, target))
    
    logger.info(f"Created {len(alerts_created)} default alerts")
    for ticker, direction, target in alerts_created:
        logger.info(f"  {ticker} {direction} ${target:,.2f}")


def print_alerts(alerts: List[Dict]):
    """Pretty print alerts"""
    if not alerts:
        print("\nNo active alerts\n")
        return
    
    print(f"\n{'ID':<6} {'Ticker':<8} {'Direction':<10} {'Target':<15} {'Current':<15} {'Status':<12} {'Created'}")
    print("-" * 90)
    
    for alert in alerts:
        current_price_str = f"${alert['current_price']:>12,.2f}" if alert['current_price'] is not None else "N/A"
        print(f"{alert['id']:<6} {alert['ticker']:<8} {alert['direction']:<10} "
              f"${alert['target_price']:>12,.2f} {current_price_str} "
              f"{alert['status']:<12} {alert['created_at'][:16] if alert['created_at'] else 'N/A'}")
    
    print()


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Crypto Price Alerts System')
    parser.add_argument('--set-alert', '-s', nargs=2, metavar=('TICKER', 'PRICE'),
                       help='Set alert (need --direction)')
    parser.add_argument('--direction', '-d', choices=['above', 'below'],
                       help='Alert direction')
    parser.add_argument('--check', '-c', action='store_true',
                       help='Check all alerts now')
    parser.add_argument('--list-alerts', '-l', action='store_true',
                       help='List active alerts')
    parser.add_argument('--cancel', type=int, metavar='ALERT_ID',
                       help='Cancel alert by ID')
    parser.add_argument('--clear-all', action='store_true',
                       help='Cancel all active alerts')
    parser.add_argument('--history', action='store_true',
                       help='Show alert history')
    parser.add_argument('--setup-defaults', action='store_true',
                       help='Set up default alerts at ±5%, ±10% levels')
    parser.add_argument('--price', '-p', metavar='TICKER',
                       help='Get current price for ticker')
    parser.add_argument('--watch', '-w', action='store_true',
                       help='Continuous monitoring mode (check every 60s)')
    parser.add_argument('--interval', '-i', type=int, default=60,
                       help='Watch interval in seconds (default: 60)')
    
    args = parser.parse_args()
    
    # Initialize database
    init_db()
    
    # Single price check
    if args.price:
        price = get_price(args.price)
        if price:
            print(f"{args.price.upper()}: ${price:,.2f}")
        else:
            print(f"Could not fetch price for {args.price}")
        return
    
    # Set alert
    if args.set_alert:
        ticker, price_str = args.set_alert
        try:
            target_price = float(price_str)
        except ValueError:
            logger.error("Price must be a number")
            return
        
        if not args.direction:
            logger.error("Must specify --direction (above/below)")
            return
        
        alert_id = set_alert(ticker, args.direction, target_price)
        if alert_id > 0:
            print(f"Alert #{alert_id} created: {ticker.upper()} {args.direction} ${target_price:,.2f}")
        return
    
    # Cancel alert
    if args.cancel:
        if cancel_alert(args.cancel):
            print(f"Alert #{args.cancel} cancelled")
        return
    
    # Clear all alerts
    if args.clear_all:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("UPDATE alerts SET status = 'cancelled' WHERE status = 'active'")
        count = cursor.rowcount
        conn.commit()
        conn.close()
        print(f"Cancelled {count} active alerts")
        return
    
    # List alerts
    if args.list_alerts:
        alerts = list_alerts()
        print_alerts(alerts)
        return
    
    # Show history
    if args.history:
        history = show_alert_history()
        if not history:
            print("\nNo alert history\n")
            return
        
        print(f"\n{'Time':<20} {'Alert ID':<10} {'Message'}")
        print("-" * 80)
        for entry in history:
            print(f"{entry['timestamp'][:19]:<20} {entry['alert_id'] or 'N/A':<10} {entry['message']}")
        print()
        return
    
    # Setup defaults
    if args.setup_defaults:
        quick_setup_default_alerts()
        return
    
    # Check alerts
    if args.check:
        triggered = check_alerts()
        if triggered:
            print(f"\n{len(triggered)} alert(s) triggered:")
            for t in triggered:
                print(f"  🚨 {t['message']}")
        else:
            print("No alerts triggered")
        return
    
    # Watch mode
    if args.watch:
        print(f"Starting continuous monitoring (every {args.interval}s)...")
        print("Press Ctrl+C to stop\n")
        try:
            while True:
                triggered = check_alerts()
                if triggered:
                    for t in triggered:
                        print(f"  🚨 {t['message']}")
                time.sleep(args.interval)
        except KeyboardInterrupt:
            print("\nMonitoring stopped")
        return
    
    # Default: just check prices
    print("Crypto Price Alerts System")
    print("=" * 40)
    print("\nUsage examples:")
    print("  python crypto_price_alerts.py --price BTC")
    print("  python crypto_price_alerts.py --set-alert BTC 62000 --direction below")
    print("  python crypto_price_alerts.py --list-alerts")
    print("  python crypto_price_alerts.py --check")
    print("  python crypto_price_alerts.py --watch")
    print("\nGet current prices:")
    prices = get_multiple_prices(['BTC', 'ETH', 'SOL'])
    for ticker, price in prices.items():
        print(f"  {ticker}: ${price:,.2f}")
    print()


if __name__ == "__main__":
    main()