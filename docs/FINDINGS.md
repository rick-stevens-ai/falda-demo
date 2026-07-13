# FALDA demo — findings for the server

Uncovered while building `falda_demo.sh` (2026-07-12). Candidate issue for
`rick-stevens-ai/falda`. Does not block the demo (the demo uses the exact enum),
but matters for API ergonomics.

> **Note:** an earlier draft of this file also reported a tenant-isolation leak on
> the `/atoms/upsert` + `/atoms/query` path. On re-test it **did not reproduce** —
> `/atoms/query` correctly isolated by tenant (secret written to `default` was not
> returned when querying as `kukla`). That finding has been removed as unconfirmed.

## `/pools/declare` accepts invalid access strings silently → read-only fallback

**Observed:** declaring a pool with `members:{kukla:"rw"}` succeeded and echoed the
roster back verbatim (`"rw"`), but a subsequent `atoms/upsert` into the pool as
`kukla` was rejected:
`{"error":"tenant kukla has read-only access to pool ...","code":"read_only"}`.

**Cause:** the access enum is `"none" | "read" | "readwrite"` (see
`src/pools.ts`). `"rw"` is not a member of the enum, so it is treated as
non-readwrite (effectively read-only) rather than rejected at declare time.

**Repro (reproduces as of 2026-07-12):**
```bash
BASE=http://<tailnet-aggregator>:8078
P="repro-$(date +%s)"
curl -s -X POST $BASE/pools/declare -H 'Content-Type: application/json' \
  -d "{\"name\":\"$P\",\"members\":{\"kukla\":\"rw\"},\"description\":\"repro\"}"
# -> declare succeeds, echoes members:{"kukla":"rw"}
curl -s -X POST $BASE/atoms/upsert -H 'Content-Type: application/json' \
  -d "{\"tenant\":\"kukla\",\"pool\":\"$P\",\"type\":\"episodic\",\"content\":\"x\",\"text\":\"x\"}"
# -> {"error":"tenant kukla has read-only access ...","code":"read_only"}
```

**Fix candidates:** (a) validate `access` against the enum in `declarePool`/`grant`
and 400 on unknown values; and/or (b) accept `"rw"`/`"ro"` as aliases.

**Workaround (used in the demo):** declare/grant with the exact enum value
`"readwrite"`.
