"""Stage 1: wide CoinGecko universe (top 500) + drawdown candidate screen.
Writes crypto_bottom_universe_v2.json
"""
import json, time, pathlib, sys
import requests
from datetime import datetime, timezone

CG = "https://api.coingecko.com/api/v3/coins/markets"
OUT = pathlib.Path.home() / "crypto_bottom_universe_v2.json"

STABLE = {"USDT","USDC","DAI","USDE","FDUSD","TUSD","USDD","PYUSD","USDS","BUIDL",
          "USD1","RLUSD","USDY","USDX","FRAX","LUSD","GUSD","EURC","USDP","SUSDE","SUSDS"}
GOLD = {"XAUT","PAXG","XAUM","KAU"}
WRAPPED = {"WBTC","WETH","STETH","WSTETH","WEETH","CBBTC","RETH","METH","LBTC","SOLVBTC",
           "WBETH","EZETH","RSETH","JITOSOL","MSOL","BNSOL","BSC-USD","WBNB","STSOL",
           "SUSDS","WSOL","CLBTC","TBTC","BTCB","RENBTC","OSETH","SWETH","ANKRETH"}

def fetch_page(page):
    r = requests.get(CG, params={
        "vs_currency":"usd","order":"market_cap_desc","per_page":250,"page":page,
        "sparkline":"false",
        "price_change_percentage":"24h,7d,30d,1y",
    }, timeout=40, headers={"accept":"application/json"})
    r.raise_for_status()
    return r.json()

def main():
    rows=[]
    for p in (1,2):
        for attempt in range(4):
            try:
                rows += fetch_page(p); break
            except Exception as e:
                print(f"page {p} attempt {attempt} failed: {e}", file=sys.stderr)
                time.sleep(8)
        time.sleep(4)
    print(f"fetched {len(rows)} rows")

    now = datetime.now(timezone.utc)
    uni=[]
    for c in rows:
        sym=(c.get("symbol") or "").upper()
        if not sym: continue
        cls="crypto"
        if sym in STABLE: cls="stablecoin"
        elif sym in GOLD: cls="gold_token"
        elif sym in WRAPPED: cls="wrapped_lst"
        athd=c.get("ath_date")
        msa=None
        if athd:
            try:
                d=datetime.fromisoformat(athd.replace("Z","+00:00"))
                msa=round((now-d).days/30.44,1)
            except Exception: pass
        uni.append({
            "symbol":sym,"id":c.get("id"),"name":c.get("name"),
            "price":c.get("current_price"),"mcap":c.get("market_cap"),
            "rank":c.get("market_cap_rank"),"vol":c.get("total_volume"),
            "ath":c.get("ath"),"ath_dd":c.get("ath_change_percentage"),
            "months_since_ath":msa,
            "p24":c.get("price_change_percentage_24h_in_currency"),
            "p7":c.get("price_change_percentage_7d_in_currency"),
            "p30":c.get("price_change_percentage_30d_in_currency"),
            "p1y":c.get("price_change_percentage_1y_in_currency"),
            "class":cls,
        })

    tradable=[u for u in uni if u["class"]=="crypto"]
    liquid=[u for u in tradable
            if (u["vol"] or 0)>=30e6 and (u["mcap"] or 0)>=2e8]
    cands=[u for u in liquid
           if (u["ath_dd"] or 0)<=-70 and (u["months_since_ath"] or 0)>=12]
    cands.sort(key=lambda x:x["ath_dd"] or 0)

    res={"generated":now.isoformat(),"n_fetched":len(rows),
         "n_tradable":len(tradable),"n_liquid":len(liquid),"n_candidates":len(cands),
         "excluded":{ "stable":[u["symbol"] for u in uni if u["class"]=="stablecoin"],
                      "gold":[u["symbol"] for u in uni if u["class"]=="gold_token"],
                      "wrapped_lst":[u["symbol"] for u in uni if u["class"]=="wrapped_lst"]},
         "universe":uni,"liquid":liquid,"candidates":cands}
    OUT.write_text(json.dumps(res,indent=1))
    print(f"tradable={len(tradable)} liquid={len(liquid)} candidates={len(cands)}")
    for c in cands[:60]:
        print(f"{c['symbol']:>8} #{c['rank'] or 0:<4} dd={c['ath_dd']:.1f}% "
              f"{c['months_since_ath']}mo px=${c['price']} vol=${(c['vol'] or 0)/1e6:.0f}M")

if __name__=="__main__":
    main()
