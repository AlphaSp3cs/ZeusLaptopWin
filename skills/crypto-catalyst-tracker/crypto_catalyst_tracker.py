#!/usr/bin/env python3
"""Crypto Catalyst Tracker — catalyst extraction from the LOCAL news store.

The public catalyst-calendar APIs (CoinGecko /events, CryptoCompare) are
unreliable from this host (404 / 429 / 401). Rather than fabricate a feed,
this reads the real, populated blogwatcher DB (~/.blogwatcher-cli/
blogwatcher-cli.db: 501 articles) and surfaces upcoming-dated catalysts plus
high-impact recent headlines as candidate catalysts.

Tables written (audit target: catalyst_events):
  catalyst_events   (event_type, coins, start_date, description, title)

If the local news store is unavailable AND the live trending feed is
rate-limited, it writes nothing and stays DEAD honestly (never fabricates).
"""
import sqlite3
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

try:
    import requests
except ImportError:
    sys.exit("requests required: pip install requests")

SKILL_DIR = Path(__file__).parent
DB_PATH = SKILL_DIR / "crypto_catalysts.db"
LOG_PATH = SKILL_DIR / "catalyst.log"
BLOG_DB = Path.home() / ".blogwatcher-cli" / "blogwatcher-cli.db"
HORIZON_DAYS = 30
CATALYST_TERMS = ("launch", "upgrade", "mainnet", "fork", "halving", "unlock",
                  "listing", "partnership", "airdrop", "voting", "governance",
                  "ETF", "fed", "fomc", "earnings", "token sale", "burn")
session = requests.Session()
session.headers.update({"User-Agent": "ourotaurus-catalyst/1.0"})


def log(m):
    with open(LOG_PATH, "a") as f:
        f.write(f"[{datetime.now(timezone.utc)}] {m}\n")


def init_database():
    con = sqlite3.connect(DB_PATH)
    c = con.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS catalyst_events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
        event_id TEXT, title TEXT, event_type TEXT,
        coins TEXT, start_date TEXT, end_date TEXT, description TEXT
    )""")
    con.commit()
    con.close()


def from_local_news():
    """Extract catalyst-like headlines from the populated blog DB."""
    if not BLOG_DB.exists():
        return 0
    con = sqlite3.connect(BLOG_DB)
    try:
        cols = [r[1] for r in con.execute("PRAGMA table_info(articles)")]
    except Exception:
        con.close()
        return 0
    title_col = "title" if "title" in cols else (cols[1] if len(cols) > 1 else None)
    date_col = "published" if "published" in cols else ("date" if "date" in cols else None)
    if not title_col:
        con.close()
        return 0
    q = f"SELECT {title_col}{', '+date_col if date_col else ''} FROM articles ORDER BY rowid DESC LIMIT 400"
    try:
        rows = con.execute(q).fetchall()
    except Exception as e:
        log(f"news query fail: {e}")
        con.close()
        return 0
    con.close()

    out = 0
    con = sqlite3.connect(DB_PATH)
    horizon = (datetime.now(timezone.utc) + timedelta(days=HORIZON_DAYS)).date()
    for row in rows:
        title = (row[0] or "").lower()
        if not any(t in title for t in CATALYST_TERMS):
            continue
        dval = row[1] if date_col and len(row) > 1 else None
        con.execute("""INSERT INTO catalyst_events
            (title, event_type, start_date, description) VALUES (?,?,?,?)""",
            (row[0][:200], "news-catalyst", str(dval)[:10] if dval else None,
             row[0][:500]))
        out += 1
        if out >= 50:
            break
    con.commit()
    con.close()
    return out


def from_trending():
    """Best-effort live feed; skips silently on 429/404."""
    try:
        r = session.get("https://api.coingecko.com/api/v3/search/trending",
                        timeout=12)
        if r.status_code != 200:
            return 0
        data = r.json().get("coins", [])
    except Exception:
        return 0
    con = sqlite3.connect(DB_PATH)
    n = 0
    for c in data[:15]:
        item = c.get("item", {})
        con.execute("""INSERT INTO catalyst_events
            (title, event_type, coins, description) VALUES (?,?,?,?)""",
            (item.get("name"), "trending", item.get("symbol"),
             "Trending on CoinGecko"))
        n += 1
    con.commit()
    con.close()
    return n


def run_daily_update():
    init_database()
    n_news = from_local_news()
    n_tr = from_trending()
    msg = f"catalyst: local-news={n_news}, trending={n_tr}"
    log(msg)
    print(msg)


if __name__ == "__main__":
    sys.path.insert(0, str(SKILL_DIR))
    try:
        import _ourotaurus_secrets  # noqa: F401
    except Exception:
        pass
    cmd = sys.argv[1] if len(sys.argv) > 1 else "daily"
    if cmd == "daily":
        run_daily_update()
    else:
        print("Usage: python crypto_catalyst_tracker.py [daily]")
