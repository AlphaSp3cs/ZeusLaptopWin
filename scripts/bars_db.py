#!/usr/bin/env python3
"""Unified OHLCV bar store for every sector. Data lives on D: per workspace law.

    python3 bars_db.py --init
    python3 bars_db.py --update                 # incremental, all sectors
    python3 bars_db.py --update --sector crypto --sector equity
    python3 bars_db.py --update --tf 1h --sector crypto
    python3 bars_db.py --status
    python3 bars_db.py --full                   # force full backfill

Design rules:
  * INCREMENTAL by default - only pulls bars newer than what we already hold.
  * A failed symbol is RECORDED as failed, never silently skipped. Silence is
    not coverage (same doctrine as signal-provenance-audit).
  * UPSERT on (symbol, tf, ts) so re-runs never duplicate.
  * VERIFIES the write actually persisted. D:\\Hermes was observed silently
    discarding a committed 1.2M-row write on 2026-08-08; a commit that
    returns cleanly is NOT proof the bytes survived.
  * Nothing here trades. It only stores bars.

SOURCE MASTER lives at C:\\Users\\victo\\bars_db.py and is mirrored to
D:\\Hermes\\workflow\\scripts\\. Never edit only the D: copy - it can vanish.
"""
import argparse
import pathlib
import shutil
import sqlite3
import sys
import time
from datetime import datetime, timezone, timedelta

try:
    import yfinance as yf
except ImportError:
    sys.exit("yfinance required: pip install yfinance")

ROOT = pathlib.Path(r"C:\Hermes\workflow")
DB = ROOT / "data" / "bars.db"
LOG = ROOT / "logs"

# ------------------------------------------------------------- universes ----
FX = ["EURUSD=X", "GBPUSD=X", "USDJPY=X", "USDCHF=X", "AUDUSD=X", "USDCAD=X",
      "NZDUSD=X", "EURGBP=X", "EURJPY=X", "GBPJPY=X", "AUDJPY=X", "EURCHF=X",
      "USDMXN=X", "USDZAR=X", "DX-Y.NYB"]

METALS = ["GC=F", "SI=F", "PL=F", "PA=F", "HG=F", "GLD", "SLV"]

ENERGY = ["BZ=F", "CL=F", "NG=F", "RB=F", "HO=F", "XLE", "USO", "UNG"]

AGS = ["ZC=F", "ZW=F", "ZS=F", "KC=F", "SB=F", "CT=F", "CC=F", "LE=F"]

INDICES = ["^GSPC", "^NDX", "^DJI", "^RUT", "^VIX", "^FTSE", "^GDAXI",
           "^FCHI", "^N225", "^HSI", "^STOXX50E", "SPY", "QQQ", "IWM", "DIA"]

BONDS = ["^TNX", "^TYX", "^FVX", "^IRX", "TLT", "IEF", "SHY", "HYG", "LQD",
         "TIP"]

DIVIDEND = ["PEP", "KO", "SCHD", "VYM", "O", "JNJ", "PG", "XOM", "CVX", "MO",
            "T", "VZ", "ABBV", "MRK", "PFE", "MMM", "CAT", "HD", "MCD", "WMT"]

SECTOR_ETFS = ["XLK", "XLF", "XLV", "XLE", "XLI", "XLY", "XLP", "XLB", "XLRE",
               "XLU", "XLC"]

# Active DCA ladder universe. These are NOT all in crypto_universe.py -
# IOTA/JTO/ENA were absent, so the ladder's own coins were invisible to the
# bar store. Registered explicitly so a ladder check can never read blind.
LADDER = ["ALGO-USD", "IOTA-USD", "JTO-USD", "ENA-USD", "NEAR-USD", "INJ-USD"]

# Confirmed delisted / acquired / no-data on 2026-08-08. Never re-register.
RETIRED = ["K", "WBA", "IAC", "IPG", "SEE", "WRK", "AGR", "SOHO", "OTRK"]


def load_equity():
    """Sector universe from the legacy C: module."""
    sys.path.insert(0, str(pathlib.Path.home()))
    try:
        import equity_sectors as es
        return sorted(set(es.ALL_EQUITY_TICKERS) | set(SECTOR_ETFS))
    except Exception:                                        # noqa: BLE001
        return SECTOR_ETFS + DIVIDEND


def load_crypto():
    sys.path.insert(0, str(pathlib.Path.home()))
    try:
        import crypto_universe as cu
        return sorted(set(cu.CRYPTO_YF_SYMBOLS) | set(LADDER))
    except Exception:                                        # noqa: BLE001
        return sorted(set(["BTC-USD", "ETH-USD", "SOL-USD", "BNB-USD",
                           "XRP-USD"]) | set(LADDER))


def universes():
    return {
        "crypto":   load_crypto(),
        "equity":   load_equity(),
        "fx":       FX,
        "metals":   METALS,
        "energy":   ENERGY,
        "ags":      AGS,
        "indices":  INDICES,
        "bonds":    BONDS,
        "dividend": DIVIDEND,
        "ladder":   LADDER,
    }


TFS = {
    "1d": ("1d", None, "5y"),
    "1h": ("1h", timedelta(days=720), "2y"),
}


SCHEMA = """
CREATE TABLE IF NOT EXISTS bars (
    symbol TEXT NOT NULL,
    tf     TEXT NOT NULL,
    ts     INTEGER NOT NULL,
    open   REAL, high REAL, low REAL, close REAL, volume REAL,
    PRIMARY KEY (symbol, tf, ts)
);
CREATE INDEX IF NOT EXISTS ix_bars_sym_tf_ts ON bars(symbol, tf, ts DESC);

CREATE TABLE IF NOT EXISTS symbols (
    symbol TEXT PRIMARY KEY,
    sector TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS symbol_tags (
    symbol TEXT NOT NULL,
    tag    TEXT NOT NULL,
    PRIMARY KEY (symbol, tag)
);

CREATE TABLE IF NOT EXISTS retired (
    symbol TEXT PRIMARY KEY, sector TEXT, reason TEXT, retired_at INTEGER
);

CREATE TABLE IF NOT EXISTS fetch_log (
    symbol TEXT NOT NULL,
    tf     TEXT NOT NULL,
    ran_at INTEGER NOT NULL,
    status TEXT NOT NULL,
    rows   INTEGER DEFAULT 0,
    detail TEXT,
    PRIMARY KEY (symbol, tf)
);
"""


def conn():
    DB.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(DB, timeout=60)
    c.execute("PRAGMA journal_mode=WAL")
    c.execute("PRAGMA synchronous=FULL")   # D: has lied about durability
    return c


def verify_persisted(expect_min_rows=1):
    """Reopen the DB from scratch and confirm rows are really on disk.

    D:\\Hermes silently discarded a fully committed multi-hundred-MB write.
    Never report success without re-reading from a fresh handle.
    """
    if not DB.exists():
        return False, "DB FILE MISSING after commit"
    try:
        c2 = sqlite3.connect(DB, timeout=30)
        n = c2.execute("SELECT COUNT(*) FROM bars").fetchone()[0]
        c2.close()
    except Exception as e:                                   # noqa: BLE001
        return False, f"reopen failed: {e}"
    if n < expect_min_rows:
        return False, f"only {n:,} rows on disk, expected >= {expect_min_rows:,}"
    return True, f"{n:,} rows verified on disk ({DB.stat().st_size / 1e6:,.0f} MB)"


def init(c):
    c.executescript(SCHEMA)
    now = int(time.time())
    c.executemany("""INSERT OR IGNORE INTO retired(symbol,sector,reason,retired_at)
                     VALUES(?,?,?,?)""",
                  [(s, "equity", "delisted/acquired/no-data", now)
                   for s in RETIRED])
    uni = universes()
    rows, tags = [], []
    for sec, syms in uni.items():
        for s in syms:
            rows.append((s, sec))
            tags.append((s, sec))
    # A symbol can live in several buckets (XLE in energy AND equity; PEP in
    # dividend AND equity). symbols.sector keeps a primary home; symbol_tags
    # records EVERY membership so coverage reporting can't understate a bucket.
    c.executemany("INSERT OR IGNORE INTO symbols(symbol,sector) VALUES(?,?)",
                  rows)
    c.executemany("INSERT OR IGNORE INTO symbol_tags(symbol,tag) VALUES(?,?)",
                  tags)
    c.execute("DELETE FROM symbols WHERE symbol IN (SELECT symbol FROM retired)")
    c.execute("DELETE FROM symbol_tags WHERE symbol IN (SELECT symbol FROM retired)")
    c.commit()
    n = c.execute("SELECT COUNT(*) FROM symbols").fetchone()[0]
    print(f"[init] schema ready, {n} symbols across {len(uni)} sectors "
          f"({len(RETIRED)} retired) -> {DB}")
    return n


def last_ts(c, sym, tf):
    r = c.execute("SELECT MAX(ts) FROM bars WHERE symbol=? AND tf=?",
                  (sym, tf)).fetchone()
    return r[0] if r and r[0] else None


def log_fetch(c, sym, tf, status, rows, detail=""):
    c.execute("""INSERT INTO fetch_log(symbol,tf,ran_at,status,rows,detail)
                 VALUES(?,?,?,?,?,?)
                 ON CONFLICT(symbol,tf) DO UPDATE SET
                   ran_at=excluded.ran_at, status=excluded.status,
                   rows=excluded.rows, detail=excluded.detail""",
              (sym, tf, int(time.time()), status, rows, detail[:300]))


def store(c, sym, tf, df):
    if df is None or len(df) == 0:
        return 0
    rows = []
    for idx, r in df.iterrows():
        try:
            ts = int(idx.timestamp())
        except Exception:                                    # noqa: BLE001
            continue
        try:
            o, h, l, cl = (float(r["Open"]), float(r["High"]),
                           float(r["Low"]), float(r["Close"]))
        except (KeyError, TypeError, ValueError):
            continue
        if cl != cl:
            continue
        v = r.get("Volume", 0)
        try:
            v = float(v)
        except (TypeError, ValueError):
            v = 0.0
        rows.append((sym, tf, ts, o, h, l, cl, v))
    if not rows:
        return 0
    c.executemany("""INSERT INTO bars(symbol,tf,ts,open,high,low,close,volume)
                     VALUES(?,?,?,?,?,?,?,?)
                     ON CONFLICT(symbol,tf,ts) DO UPDATE SET
                       open=excluded.open, high=excluded.high,
                       low=excluded.low, close=excluded.close,
                       volume=excluded.volume""", rows)
    return len(rows)


def fetch_symbol(c, sym, tf, full=False):
    interval, maxback, period = TFS[tf]
    now = datetime.now(timezone.utc)
    kw = {"interval": interval, "auto_adjust": True, "progress": False}
    lt = None if full else last_ts(c, sym, tf)
    if lt:
        start = datetime.fromtimestamp(lt, timezone.utc) - timedelta(days=2)
        if maxback and start < now - maxback:
            start = now - maxback + timedelta(days=1)
        if start >= now - timedelta(hours=1):
            return "OK", 0, "already current"
        kw["start"] = start.strftime("%Y-%m-%d")
    else:
        kw["period"] = period
    try:
        df = yf.download(sym, threads=False, **kw)
        if df is None or len(df) == 0:
            return "EMPTY", 0, "no rows returned"
        if hasattr(df.columns, "nlevels") and df.columns.nlevels > 1:
            df.columns = df.columns.get_level_values(0)
        n = store(c, sym, tf, df)
        return ("OK" if n else "EMPTY"), n, ""
    except Exception as e:                                   # noqa: BLE001
        return "ERROR", 0, str(e)


def update(c, sectors=None, tfs=("1d",), full=False):
    q = "SELECT symbol,sector FROM symbols"
    args = []
    if sectors:
        q = ("SELECT DISTINCT t.symbol, t.tag FROM symbol_tags t "
             "WHERE t.tag IN (%s)" % ",".join("?" * len(sectors)))
        args = list(sectors)
    syms = c.execute(q + " ORDER BY 2,1", args).fetchall()
    if not syms:
        print("[update] no symbols matched - run --init first")
        return 1

    before = c.execute("SELECT COUNT(*) FROM bars").fetchone()[0]
    tot = {"OK": 0, "EMPTY": 0, "ERROR": 0}
    bars_new = 0
    failures = []
    t0 = time.time()
    print(f"[update] {len(syms)} symbols x {len(tfs)} timeframe(s), "
          f"{'FULL backfill' if full else 'incremental'}")

    for i, (sym, sec) in enumerate(syms, 1):
        for tf in tfs:
            st, n, det = fetch_symbol(c, sym, tf, full)
            log_fetch(c, sym, tf, st, n, det)
            tot[st] += 1
            bars_new += n
            if st != "OK":
                failures.append((sym, sec, tf, st, det[:80]))
        if i % 25 == 0:
            c.commit()
            print(f"  {i}/{len(syms)}  {bars_new:,} bars  "
                  f"{time.time() - t0:.0f}s  ok={tot['OK']} "
                  f"empty={tot['EMPTY']} err={tot['ERROR']}")
    c.commit()

    print(f"\n[update] done in {time.time() - t0:.0f}s - {bars_new:,} bars "
          f"written/updated")
    print(f"  OK {tot['OK']}   EMPTY {tot['EMPTY']}   ERROR {tot['ERROR']}")

    ok, msg = verify_persisted(max(before, 1))
    print(f"  [persistence] {'VERIFIED' if ok else 'FAILED'} - {msg}")
    if not ok:
        print("  !! THE WRITE DID NOT SURVIVE. Treat this store as EMPTY.")
        print("  !! Do not scan against it. Check drive health before retrying.")

    if failures:
        print(f"\n  !! {len(failures)} symbol/tf pairs did NOT deliver data.")
        print("  !! These are UNCOVERED. Their absence from a scan is not "
              "'no signal'.")
        for s, sec, tf, st, det in failures[:30]:
            print(f"     {s:<12} {sec:<9} {tf}  {st}  {det}")
        if len(failures) > 30:
            print(f"     ... and {len(failures) - 30} more (see --status)")
    return 0 if ok else 1


def status(c):
    now = int(time.time())
    print("=" * 78)
    print(f"BARS DB  {DB}")
    sz = DB.stat().st_size / 1e6 if DB.exists() else 0
    tot = c.execute("SELECT COUNT(*) FROM bars").fetchone()[0]
    nsym = c.execute("SELECT COUNT(DISTINCT symbol) FROM bars").fetchone()[0]
    reg = c.execute("SELECT COUNT(*) FROM symbols").fetchone()[0]
    print(f"size {sz:,.1f} MB   {tot:,} bars   {nsym}/{reg} symbols with data")
    for tf, n, s in c.execute(
            "SELECT tf,COUNT(*),COUNT(DISTINCT symbol) FROM bars GROUP BY tf"):
        print(f"   {tf}: {n:,} bars across {s} symbols")
    print("=" * 78)
    print(f"{'sector':<10} {'syms':>5} {'covered':>8} {'bars':>10} "
          f"{'newest bar':>20} {'stale?':>8}")
    print("-" * 78)
    for sec, in c.execute("SELECT DISTINCT tag FROM symbol_tags ORDER BY 1"):
        n, cov, nb, mx = c.execute("""
            SELECT COUNT(DISTINCT t.symbol), COUNT(DISTINCT b.symbol),
                   COUNT(b.ts), MAX(b.ts)
            FROM symbol_tags t LEFT JOIN bars b ON b.symbol=t.symbol
            WHERE t.tag=?""", (sec,)).fetchone()
        if mx:
            age_h = (now - mx) / 3600
            newest = datetime.fromtimestamp(mx, timezone.utc).strftime(
                "%Y-%m-%d %H:%M")
            flag = "OK" if age_h < 96 else f"{age_h / 24:.0f}d"
        else:
            newest, flag = "-", "NO DATA"
        print(f"{sec:<10} {n:>5} {cov:>8} {nb:>10,} {newest:>20} {flag:>8}")

    bad = c.execute("""SELECT status,COUNT(*) FROM fetch_log
                       WHERE status!='OK' GROUP BY status""").fetchall()
    if bad:
        print("\nUNCOVERED (last run):")
        for st, n in bad:
            print(f"  {st}: {n}")
        print("  !! Missing data is NOT a passing check.")
    return 0


def mirror_source():
    """Keep a C: master copy - D: has destroyed this file once already."""
    try:
        me = pathlib.Path(__file__).resolve()
        master = pathlib.Path.home() / me.name
        if me != master and (not master.exists()
                             or master.read_bytes() != me.read_bytes()):
            shutil.copy2(me, master)
    except Exception:                                        # noqa: BLE001
        pass


def main():
    ap = argparse.ArgumentParser(description="Unified bar store (D:\\Hermes)")
    ap.add_argument("--init", action="store_true")
    ap.add_argument("--update", action="store_true")
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--full", action="store_true")
    ap.add_argument("--sector", action="append")
    ap.add_argument("--tf", action="append", choices=list(TFS))
    a = ap.parse_args()

    LOG.mkdir(parents=True, exist_ok=True)
    mirror_source()
    c = conn()
    c.executescript(SCHEMA)

    rc = 0
    if a.init:
        init(c)
    if a.update:
        rc = update(c, a.sector, tuple(a.tf or ["1d"]), a.full)
    if a.status or not (a.init or a.update):
        status(c)
    c.close()
    return rc


if __name__ == "__main__":
    sys.exit(main())
