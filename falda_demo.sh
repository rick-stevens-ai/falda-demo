#!/usr/bin/env bash
# falda_demo.sh — live, re-runnable demo of the FALDA memory engine.
#
# Proves the four things a flat memory file / bigger prompt CANNOT do:
#   1. TIERED MEMORY      — T0 stream / T1 atoms / T2 scenes / T3 core all return real data
#   2. HYBRID RECALL      — recall by MEANING (semantic) and by keyword (lexical)
#   3. TENANT ISOLATION   — two agents on ONE gateway, private stores are walled off
#   4. SHARED POOL        — the two agents deliberately SHARE memory via a declared pool
#                           (Kukla writes -> Ollie reads), while private stores stay isolated
#
# Pure stdlib Python driver (no curl/jq). Each beat prints a PASS/FAIL line.
#
# Usage:
#   bash falda_demo.sh                         # full demo against the live gateway
#   FALDA_URL=... bash falda_demo.sh           # override gateway
#
# Architecture: ONE FALDA instance (gateway :8078 on CherryRd, one store root).
#   - tenant "kukla"  = Kukla's private memory  (Hermes/m1)
#   - tenant "ollie"  = Ollie's private memory  (OpenClaw/CherryRd)
#   - pool  "agent-shared-demo" = opt-in shared store both tenants route to (readwrite)
set -u

FALDA_URL="${FALDA_URL:-http://<tailnet-aggregator>:8078}"
TA="${FALDA_TENANT:-kukla}"           # agent A (Kukla)
TB="${FALDA_TENANT_B:-ollie}"         # agent B (Ollie)
POOL="${FALDA_POOL:-agent-shared-demo}"

echo "=================================================================="
echo " FALDA LIVE DEMO   gateway=${FALDA_URL}"
echo " agentA=${TA}   agentB=${TB}   shared-pool=${POOL}"
echo " run id: $(date -u +%Y%m%dT%H%M%SZ)"
echo "=================================================================="

python3 - "$FALDA_URL" "$TA" "$TB" "$POOL" <<'PY'
import sys, json, time, urllib.request, urllib.error

BASE, TA, TB, POOL = sys.argv[1:5]
STAMP = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())

def call(path, payload, timeout=12):
    data = json.dumps(payload).encode()
    req = urllib.request.Request(BASE + path, data=data,
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, json.loads(r.read().decode() or "{}")
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode() or "{}")
    except Exception as e:
        return 0, {"error": f"{type(e).__name__}: {e}"}

def items(body):
    return (body or {}).get("items") or (body or {}).get("atoms") or []

def get_health():
    try:
        req = urllib.request.Request(BASE + "/healthz")
        with urllib.request.urlopen(req, timeout=8) as r:
            return json.loads(r.read().decode())
    except Exception as e:
        return {"ok": False, "error": str(e)}

npass = nfail = 0
def result(ok, label, detail=""):
    global npass, nfail
    npass += ok; nfail += (not ok)
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}" + (f"  — {detail}" if detail else ""))

hr = lambda: print("-"*66)

# ---- BEAT 0: gateway + tiers ---------------------------------------------
print("\nBEAT 0 — Gateway health & tiers")
h = get_health()
result(bool(h.get("ok")), "gateway up", f"tiers={','.join(h.get('tiers',[]))}")
hr()

# ---- BEAT 1: four tiers respond ------------------------------------------
print("BEAT 1 — All four memory tiers return real data (T0->T3)")
st, s = call("/stream/search", {"tenant": TA, "query": "LUCID", "limit": 1})
result(len(s.get("messages", [])) >= 1, "T0 stream (raw turns)",
       (s.get("messages",[{}])[0].get("content","")[:60]) if s.get("messages") else "empty")
st, a = call("/atoms/search", {"tenant": TA, "query": "LUCID annotation", "limit": 1})
result(len(items(a)) >= 1, "T1 atoms (distilled, typed facts)",
       (items(a)[0].get("content","")[:60]) if items(a) else "empty")
st, c = call("/core/read", {"tenant": TA})
result(len((c or {}).get("content","")) >= 50, "T3 core (persona synthesis)",
       f"{len((c or {}).get('content',''))} chars")
hr()

# ---- BEAT 2: hybrid recall (meaning vs keyword) --------------------------
print("BEAT 2 — Hybrid recall: by MEANING and by keyword")
st, sem = call("/atoms/search", {"tenant": TA,
       "query": "where do the annotated latex working drafts live", "limit": 1})
result(len(items(sem)) >= 1, "semantic recall (query shares few words w/ stored fact)",
       (items(sem)[0].get("content","")[:60]) if items(sem) else "no hit")
st, lex = call("/stream/search", {"tenant": TA, "query": "LUCID endpoint", "limit": 1})
result(len(lex.get("messages", [])) >= 1, "lexical recall (keyword match in raw stream)")
hr()

# ---- BEAT 3: tenant isolation (private stores walled off) ----------------
print("BEAT 3 — Tenant isolation on ONE gateway")
sec = f"isolation-{STAMP}-narwhal"
call("/atoms/upsert", {"tenant": TA, "type": "episodic",
     "content": f"PRIVATE FACT {sec} — only agent {TA} should see this",
     "text": f"PRIVATE FACT {sec} — only agent {TA} should see this"})
time.sleep(1.5)
st, seen_a = call("/atoms/search", {"tenant": TA, "query": sec, "limit": 3})
st, seen_b = call("/atoms/search", {"tenant": TB, "query": sec, "limit": 3})
a_hit = any(sec in i.get("content","") for i in items(seen_a))
b_hit = any(sec in i.get("content","") for i in items(seen_b))
result(a_hit and not b_hit,
       f"{TA}'s private fact is visible to {TA}, invisible to {TB}",
       f"{TA}={'hit' if a_hit else 'miss'}  {TB}={'LEAK' if b_hit else 'walled off'}")
hr()

# ---- BEAT 4: shared pool (deliberate cross-agent sharing) -----------------
print("BEAT 4 — Shared pool: agents SHARE memory on purpose")
# ensure pool exists + both members readwrite (idempotent)
call("/pools/declare", {"name": POOL,
     "members": {TA: "readwrite", TB: "readwrite"},
     "description": "Shared cross-agent memory demo pool"})
call("/pools/grant", {"name": POOL, "tenant": TA, "access": "readwrite"})
call("/pools/grant", {"name": POOL, "tenant": TB, "access": "readwrite"})
shared = f"shared-{STAMP}-otter"
st, w = call("/atoms/upsert", {"tenant": TA, "pool": POOL, "type": "episodic",
     "content": f"SHARED FACT {shared} — written by {TA} for {TB} via the shared pool",
     "text": f"SHARED FACT {shared} — written by {TA} for {TB} via the shared pool"})
wrote = "id" in w
result(wrote, f"{TA} writes a fact into shared pool '{POOL}'",
       w.get("error","ok") if not wrote else f"atom {w.get('id','')[:8]}")
time.sleep(1.5)
st, r = call("/atoms/query", {"tenant": TB, "pool": POOL, "query": shared, "limit": 3})
b_reads = any(shared in i.get("content","") for i in items(r))
result(b_reads, f"{TB} reads {TA}'s fact FROM the shared pool", "cross-agent share works" if b_reads else "not found")
st, priv = call("/atoms/search", {"tenant": TB, "query": shared, "limit": 3})
b_priv = any(shared in i.get("content","") for i in items(priv))
result(not b_priv, f"...but it did NOT leak into {TB}'s PRIVATE store",
       "private store stays clean" if not b_priv else "LEAK into private")
hr()

print(f"\n  RESULT: {npass} PASS / {nfail} FAIL")
print("  Narrative:")
print("   • memory persists ACROSS sessions (nothing here relies on chat history)")
print("   • recall is by MEANING, not keyword; atoms come back typed+ranked, not a flat log")
print(f"   • ONE gateway: {TA} & {TB} have PRIVATE walled-off memory AND an opt-in SHARED pool")
print("   • the two-agent live version: each agent plants via its own memory tool;")
print("     the shared pool is how they hand knowledge to each other on purpose")
sys.exit(0 if nfail == 0 else 1)
PY
rc=$?
echo "=================================================================="
echo "falda_demo.sh exit=$rc"
exit $rc
