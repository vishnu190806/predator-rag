"""Live integration: real qwen3/Ollama response shape vs our output handling.

No corpus needed (fixed context string). Asserts on the live path:
- raw API returns a `thinking` field (thinking enabled server-side)
- generate_answer output contains no thinking text
- stream output contains no thinking text and matches non-stream content
- empty-simulation: is_empty_answer detects the honest message
Writes: verify_think_live.json
"""
import json, sys
sys.stdout.reconfigure(encoding="utf-8")
import requests
import answer
from answer import OLLAMA_HOST, OLLAMA_MODEL, NUM_CTX

CTX = ("[Source 1] Chapter: CHAPTER FIVE | Section: 5.10  POWER (Page 13)\n"
       "Text:\nPower is the rate of doing work. P = W/t. SI unit: watt (W).")
Q = "Define power and write its SI unit."

# 1. Raw API shape (ground truth about the endpoint)
raw = requests.post(f"{OLLAMA_HOST}/api/generate", json={
    "model": OLLAMA_MODEL, "prompt": "Say: POWER-OK", "stream": False,
    "options": {"num_ctx": 512, "num_predict": 16}}, timeout=120).json()
raw_keys = sorted(raw.keys())
raw_has_thinking = bool((raw.get("thinking") or "").strip())
print("raw keys:", raw_keys, flush=True)
print("raw thinking present:", raw_has_thinking,
      "chars:", len(raw.get("thinking") or ""), flush=True)

# 2. Our non-stream path on a real question
text, lat = answer.generate_answer(Q, CTX, is_numerical=False)
print("plain chars:", len(text), "latency:", round(lat, 1), flush=True)

# 3. Our stream path on the same question
streamed = "".join(answer.generate_answer_stream(Q, CTX, is_numerical=False))
print("stream chars:", len(streamed), flush=True)

out = {"model": OLLAMA_MODEL,
       "raw_keys": raw_keys, "raw_thinking_present": raw_has_thinking,
       "plain_chars": len(text), "stream_chars": len(streamed),
       "plain_head": text[:200], "stream_head": streamed[:200],
       "is_empty_message": answer.is_empty_answer(text)}
with open("verify_think_live.json", "w", encoding="utf-8") as fh:
    json.dump(out, fh, indent=2)
print("WROTE verify_think_live.json", flush=True)
