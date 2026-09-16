#!/usr/bin/env python3
"""Direct RSS news parser — no Firecrawl, no billing needed."""
import urllib.request, json, re, html
from datetime import datetime, timezone
import xml.etree.ElementTree as ET

HEADERS = {"User-Agent": "Mozilla/5.0 (Hermes News Aggregator)"}

FEEDS = [
    ("BBC World", "http://feeds.bbci.co.uk/news/world/rss.xml"),
    ("BBC Business", "http://feeds.bbci.co.uk/news/business/rss.xml"),
    ("NYT World", "https://rss.nytimes.com/services/xml/rss/nyt/World.xml"),
    ("NYT Business", "https://rss.nytimes.com/services/xml/rss/nyt/Business.xml"),
    ("Reuters World", "https://www.reutersagency.com/feed/"),
    ("Yahoo Finance", "https://finance.yahoo.com/rindex"),
    ("CNBC", "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=100003114"),
    ("MarketWatch", "https://www.marketwatch.com/rss/topstories"),
    ("WSJ Markets", "https://feeds.a.dj.com/rss/RSSMarketsMain.xml"),
    ("FT", "https://www.ft.com/rss/home"),
    ("The Economist", "https://www.economist.com/rss/the_world_this_week_rss.xml"),
    ("Al Jazeera", "https://www.aljazeera.com/xml/rss/all.xml"),
    ("AP News", "https://rsshub.app/apnews/topics/top-news"),
    ("The Guardian", "https://www.theguardian.com/world/rss"),
    ("Nikkei Asia", "https://asia.nikkei.com/rss"),
    ("South China Morning Post", "https://www.scmp.com/rss/91/feed"),
    ("The Hindu", "https://www.thehindu.com/news/international/feeder/default.rss"),
    ("Globes Israel", "https://www.globes.co.il/en/main/rss.xml"),
    ("Russia Today", "https://www.rt.com/rss/news/"),
    ("China Daily", "https://www.chinadaily.com.cn/rss/world_rss.xml"),
]

def fetch_feed(name, url):
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=15) as r:
            data = r.read().decode("utf-8", errors="ignore")
        return data
    except Exception as e:
        return None

def parse_rss(xml_data):
    items = []
    try:
        root = ET.fromstring(xml_data)
        for item in root.iter("item"):
            title = item.findtext("title", "").strip()
            desc = item.findtext("description", "").strip()
            pub_date = item.findtext("pubDate", "")
            link = item.findtext("link", "")
            if title:
                items.append({
                    "title": title,
                    "description": re.sub(r"<[^>]+>", "", desc)[:200],
                    "published": pub_date,
                    "link": link,
                })
    except Exception as e:
        pass
    return items

def fetch_headline_scrape():
    """Fallback: scrape headline text from major news sites directly."""
    sites = [
        ("CNN", "https://lite.cnn.com"),
        ("The Guardian", "https://www.theguardian.com/uk"),
        ("ABC News", "https://abcnews.go.com"),
        ("CBS News", "https://www.cbsnews.com"),
        ("NBC News", "https://www.nbcnews.com"),
        ("Sky News", "https://news.sky.com"),
        ("France24", "https://www.france24.com/en/"),
        ("Deutsche Welle", "https://www.dw.com/en/top-stories/s-9097"),
    ]
    results = {}
    for name, url in sites:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=15) as r:
                html = r.read().decode("utf-8", errors="ignore")
            titles = re.findall(r'<(?:h[1-3]|a)[^>]*>([^<]{20,150})</(?:h[1-3]|a)>', html)
            clean = []
            for t in titles:
                t = re.sub(r"<[^>]+>", "", t).strip()
                if len(t) > 20 and len(t) < 150 and not t.startswith(("http", "www", "{", "[")):
                    clean.append(t)
            if clean:
                results[name] = clean[:15]
        except Exception as e:
            pass
    return results

def main():
    print("=" * 70)
    print("COMPREHENSIVE WORLD NEWS AGGREGATOR")
    print("=" * 70)
    
    all_headlines = {}
    
    # RSS feeds
    print("\n[1/2] Fetching RSS feeds...")
    for name, url in FEEDS:
        print(f"  {name}...", end=" ")
        xml = fetch_feed(name, url)
        if xml:
            items = parse_rss(xml)
            if items:
                all_headlines[name] = items[:15]
                print(f"OK ({len(items)} stories)")
            else:
                print("EMPTY")
        else:
            print("FAIL")
    
    # Direct HTML scraping
    print("\n[2/2] Direct HTML scraping from major news sites...")
    scrape = fetch_headline_scrape()
    for name, titles in scrape.items():
        if titles:
            all_headlines[name] = [{"title": t, "source": name} for t in titles[:15]]
            print(f"  {name}: {len(titles)} headlines")
    
    # Print
    print(f"\n{'=' * 70}")
    print(f"HEADLINES BY SOURCE")
    print(f"{'=' * 70}")
    
    for source, items in all_headlines.items():
        print(f"\n>>> {source}")
        for i, item in enumerate(items[:10]):
            if isinstance(item, dict):
                title = item.get("title", "")
                print(f"  {i+1:>2}. {title}")
    
    # Save
    output = {
        "scan_timestamp": datetime.now(timezone.utc).isoformat(),
        "sources_count": len(all_headlines),
        "headlines": all_headlines,
    }
    with open(r"C:\Hermes\workflow\data\news_headlines.json", "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, default=str, ensure_ascii=False)
    print(f"\nSaved to: C:\\Hermes\\workflow\\data\\news_headlines.json")

if __name__ == "__main__":
    main()
