# FALDA demo — findings for the server

Uncovered while building `falda_demo.sh` (2026-07-12). Both are candidate issues
for `rick-stevens-ai/falda`. Neither blocks the demo (the demo routes around
them), but they matter for correctness.

## 1. `/atoms/upsert` + `/atoms/query` do not tenant-scope the way `/atoms/search` does

**Observed:** a fact written via `POST /atoms/upsert {tenant:"default", ...}` and
then read via `POST /atoms/query {tenant:"kukla", ...}` (a *different* tenant,
**no pool** specified) was returned — i.e. the upsert/query pair appears to read
a shared/global atom index rather than the per-tenant private store.

Meanwhile `POST /atoms/search {tenant:"kukla", ...}` correctly isolates: a fact
in tenant `kukla` returns 0 hits when queried as tenant `ollie`.

**Repro:**
```bash
BASE=http://<tailnet-aggregator>:8078
SEC="isotest-$(date +%s)"
curl -s -X POST $BASE/atoms/upsert -H 'Content-Type: application/json' \
  -d "{\"tenant\":\"default\",\"type\":\"episodic\",\"content\":\"$SEC\",\"text\":\"$SEC\"}"
# then, DIFFERENT tenant, NO pool:
curl -s -X POST $BASE/atoms/query  -H 'Content-Type: application/json' \
  -d "{\"tenant\":\"kukla\",\"query\":\"$SEC\",\"limit\":3}"   # <-- returns the secret (leak)
curl -s -X POST $BASE/atoms/search -H 'Content-Type: application/json' \
  -d "{\"tenant\":\"kukla\",\"query\":\"$SEC\",\"limit\":3}"   # <-- correctly 0 hits
```

A query to a *nonexistent* tenant returns 0, so **some** filtering exists on the
query path — but it is not equivalent to `search`'s per-tenant store routing.

**Impact:** anything demoing/relying on isolation must use `/atoms/search` (the
path the Hermes provider uses), not `/atoms/query`, until upsert/query route
writes+reads through the same per-tenant store `search` uses.

**Why the demo is unaffected:** `falda_demo.sh` proves private isolation via
`/atoms/search` (Beat 3) and proves *deliberate* sharing via an explicitly
declared **pool** (Beat 4). The pool path is correct — writes land in
`root/pools/<pool>/` and are visible to member tenants only.

## 2. `/pools/declare` accepts invalid access strings silently → read-only fallback

**Observed:** declaring a pool with `members:{kukla:"rw", ollie:"rw"}` succeeded
and echoed the roster back verbatim (`"rw"`), but a subsequent `atoms/upsert`
into the pool as `kukla` was rejected:
`{"error":"tenant kukla has read-only access to pool ...","code":"read_only"}`.

**Cause:** the access enum is `"none" | "read" | "readwrite"` (see
`src/pools.ts`). `"rw"` is not a member of the enum, so it is treated as
non-readwrite (effectively read-only) rather than rejected at declare time.

**Fix candidates:** (a) validate `access` against the enum in `declarePool`/`grant`
and 400 on unknown values; and/or (b) accept `"rw"`/`"ro"` as aliases.

**Workaround (used in the demo):** declare/grant with the exact enum value
`"readwrite"`.
