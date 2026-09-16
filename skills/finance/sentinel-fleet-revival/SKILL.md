---
name: sentinel-fleet-revival
description: "Revive DEAD sentinels with a real keyless API."
user-invocable: true
metadata:
  version: "1.0"
  tags: ["trading", "sentinels", "data-quality", "revival", "provenance"]
---

# Sentinel Fleet Revival

A DEAD sentinel is almost never a wiring problem — it's an **empty engine body**.
Behind a `CREATE TABLE` + `exit 0` wrapper, every data function is `pass` / `TODO`.
Registration, cron, key-bridging, gateway-restart — none of it makes it produce rows.
The code that fetches is simply absent. Fix = rebuild the body with a real, keyless
public API, then let `sentinel_audit.py` prove it.

## When to use
- `python3 ~/sentinel_audit.py` shows a sentinel as DEAD/STALE and you want it live.
- A skill "exists" but its DB tables are empty after a run.
- Before trusting any confluence that names a sentinel you haven't proven this session.

## Revival procedure (proven 2026-08-08: 1/10 -> 5/10 LIVE)
1. Run `python3 ~/sentinel_audit.py` to get the fleet status and target tables.
2. Open the engine at `~/.hermes/skills/<name>/<engine>.py`. If the data functions
   are `pass`/`TODO`, it's a scaffold — confirm with `grep -c "TODO" <engine>.py`.
3. Replace the stub functions with a real fetcher from `references/keyless_apis.md`
   (Binance futures, DeFiLlama, and the local blogwatcher news store all work keyless).
4. **DELETE the stale `.db`** before the first run — old scaffolds leave a differently
   shaped DB that `CREATE TABLE IF NOT EXISTS` won't rebuild, so the first INSERT
   throws "no column named X" / "NOT NULL constraint failed".
5. Run the engine. Re-run `sentinel_audit.py` — it should flip to LIVE (rows present,
   DB fresh).
6. **Sync to the enabled dir:** copy the engine + fresh `.db` to
   `~/AppData/Local/hermes/skills/<name>/` too, or `hermes skills` keeps the old code.
7. Add a `> **STATUS: LIVE (audited YYYY-MM-DD).**` banner to the top of SKILL.md so
   the provenance state is visible at a glance.

## Honest DEAD is correct
If a source needs a paid key (Glassnode/on-chain, TokenUnlocks) or a populated broker
DB (trading-risk-dashboard -> positions.db) that doesn't exist here, **leave it DEAD**
and mark SKILL.md. Never fabricate rows to flip the audit — that's the exact trap
signal-provenance-audit exists to catch. Four sentinels stayed DEAD on 2026-08-08;
that was the right outcome, not a failure.

## Pitfalls
- Stale `.db` schema trap (above) — delete before first real run.
- Two skills dirs — sync source + enabled copies.
- CoinGecko `/events`=404, `/search/trending`=429: don't build a catalyst feed on it;
  use the local blogwatcher news store instead.
- A silent script with exit 0 is the MOST dangerous state.

## Support files
- `references/keyless_apis.md` — verified HTTP-200 no-key endpoints + payload shapes
  for Binance futures, DeFiLlama, and the local news store. Reuse before writing a
  new fetcher.

See also: signal-provenance-audit (detection + the never-fake-a-default rule).
