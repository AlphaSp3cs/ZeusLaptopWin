"""Stage 2: yfinance cross-check + base-quality score for bottom candidates."""
import json, pathlib, warnings, sys
import numpy as np, pandas as pd, yfinance as yf
warnings.filterwarnings("ignore")

HOME = pathlib.Path.home()
UNI = json.loads((HOME/"crypto_bottom_universe_v2.json").read_text())
OUT = HOME/"crypto_base_quality_v2.json"

def series(sym):
    try:
        df = yf.download(f"{sym}-USD", period="10y", interval="1d",
                         auto_adjust=False, progress=False, threads=False)
    except Exception as e:
        return None, f"fetch_err:{e}"
    if df is None or len(df)==0: return None, "empty"
    if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
    df = df.dropna(subset=["Close"])
    if len(df) < 500: return None, f"short:{len(df)}bars"
    return df, None

rows=[]; dropped=[]
for c in UNI["candidates"]:
    sym=c["symbol"]; cg=c["price"]
    df,err = series(sym)
    if err: dropped.append({"symbol":sym,"reason":err}); continue
    close=df["Close"].astype(float)
    last=float(close.iloc[-1])
    if not cg or abs(last/cg-1)>0.15:
        dropped.append({"symbol":sym,"reason":f"price_mismatch yf={last:.6g} cg={cg:.6g}"}); continue

    ath_i=int(close.values.argmax()); ath=float(close.iloc[ath_i])
    post=close.iloc[ath_i:]
    if len(post)<120: dropped.append({"symbol":sym,"reason":"no_post_ath_history"}); continue
    low_i=int(post.values.argmin()); low=float(post.iloc[low_i])
    low_date=post.index[low_i]
    months_off_low=round((close.index[-1]-low_date).days/30.44,1)

    ma50=close.rolling(50).mean(); ma200=close.rolling(200).mean()
    m50=float(ma50.iloc[-1]); m200=float(ma200.iloc[-1])
    slope90 = float(ma200.iloc[-1]/ma200.iloc[-91]-1) if len(ma200.dropna())>91 else None
    off_low = last/low-1
    higher_low = float(close.iloc[-90:].min()) > low*1.15
    vol30 = float(close.pct_change().iloc[-30:].std()*np.sqrt(365))

    s = (0.30*(off_low>0.20) + 0.20*(last>m200) + 0.15*(last>m50)
         + 0.15*((slope90 or -1)>0) + 0.10*higher_low + 0.10*(months_off_low>6))
    rows.append({"symbol":sym,"rank":c["rank"],"cg_price":cg,"yf_last":last,
        "ath_dd":c["ath_dd"],"months_since_ath":c["months_since_ath"],
        "cycle_low":low,"low_date":str(low_date.date()),"months_off_low":months_off_low,
        "off_low_pct":round(off_low*100,1),"px_gt_ma200":bool(last>m200),
        "px_gt_ma50":bool(last>m50),"ma200_slope90":round(slope90,4) if slope90 is not None else None,
        "higher_low":bool(higher_low),"ann_vol30":round(vol30,3),
        "base_score":round(100*s,1),"bars":len(close)})

rows.sort(key=lambda r:(-r["base_score"], r["ath_dd"]))
OUT.write_text(json.dumps({"scored":rows,"dropped":dropped},indent=1))
print(f"scored={len(rows)} dropped={len(dropped)}\n")
print(f"{'SYM':>8} {'score':>6} {'dd%':>7} {'offLow%':>8} {'moOffLow':>8} {'>MA200':>7} {'>MA50':>6} {'slope90':>8} {'HL':>3}")
for r in rows:
    print(f"{r['symbol']:>8} {r['base_score']:>6} {r['ath_dd']:>7.1f} {r['off_low_pct']:>8.1f} "
          f"{r['months_off_low']:>8} {str(r['px_gt_ma200']):>7} {str(r['px_gt_ma50']):>6} "
          f"{str(r['ma200_slope90']):>8} {str(r['higher_low']):>3}")
print("\nDROPPED:")
for d in dropped: print(f"  {d['symbol']:>8}  {d['reason']}")
