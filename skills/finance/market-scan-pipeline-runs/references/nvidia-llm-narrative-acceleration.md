# NVIDIA text-LLM: accelerating the scan report's narrative layer

## What it is / what it is NOT
- User supplied a NVIDIA hosted inference key (NVAKEY). Endpoint is OpenAI-compatible
  chat-completions: `https://integrate.api.nvidia.com/v1/chat/completions`.
- It is a TEXT/LLM endpoint ONLY. It does NOT accelerate the numeric scan/gate/gauge
  math (yfinance fetches, R:R checks, VWAP, the gate's 7 hard checks). Its value is
  the INTERPRETATION layer: turning gate JSON + danger-zone gauge + blogwatcher into
  a plain-English regime read + per-setup rationale.
- Inject the key via env `NVAKEY` (or `NVAPI`). The key rotates per session — do not
  persist the value; re-set it each run.

## Account-catalog models (verified 2026-08-05)
- `meta/llama-3.1-8b-instruct`  -> ~1-2s per call. USE AS FAST DEFAULT.
- `nvidia/llama-3.3-nemotron-super-49b-v1` -> ~30s. Quality, not speed.
- `openai/gpt-oss-120b` -> timed out on this account.
- Several other slugs 404 (not in this account's catalog). Probe with the curl below
  before assuming a model name works.

## How to use it in the pipeline
- Reusable client: `scripts/nvidia_llm.py`, function
  `synthesize_nightshift(scan_data, gate_results, catalysts, gauge)`.
- It batches EVERY GO + WATCH setup into ONE call (instead of reasoning about each
  separately), and the call can run in parallel with the rest of the report assembly.
- Result is content-hash cached (`.nvidia_llm_cache/`), so re-builds of identical
  data return in 0.0s. NO-GO setups get no narrative (no rationale needed).
- Gauge direction MUST be stated explicitly in the prompt (see pitfall). The
  `synthesize_nightshift` prompt carries a "CRITICAL DIRECTION RULE" for this.

## PITFALL: the LLM inverts the gauge direction
- On first run the 8B model wrote "gauge 82.5 implies a HIGH risk appetite" — BACKWARDS.
  In this stack, higher gauge = MORE danger = LOWER risk appetite (gauge ~82-100 =
  EXTREME DANGER -> suppress risk, hedge). The model defaults to the lay reading
  ("high number = aggressive").
- FIX: the prompt MUST contain an explicit direction rule. Any LLM delegated to read
  the danger-zone gauge must be told the sign, or it will invert it.

## Probe / test snippet
```bash
export NVAKEY="nvapi-..."
export NVIDIA_MODEL="meta/llama-3.1-8b-instruct"
# probe which models resolve on this account:
for M in "meta/llama-3.1-8b-instruct" "nvidia/llama-3.3-nemotron-super-49b-v1"; do
  echo "=== $M ==="
  curl -s --max-time 40 https://integrate.api.nvidia.com/v1/chat/completions \
    -H "Authorization: Bearer $NVAKEY" -H "Content-Type: application/json" \
    -d "{\"model\":\"$M\",\"messages\":[{\"role\":\"user\",\"content\":\"say ok\"}],\"max_tokens\":5}" | head -c 200
  echo
done
# run the client against the latest scan artifacts:
cd /c/Users/victo && python3 nvidia_llm.py
```
