# FALDA Demo

Live, re-runnable demonstration of the **FALDA** memory engine — the four-tier
(stream / atoms / scenes / core) hybrid-recall memory system that backs Rick
Stevens' lab agents (Kukla on Hermes/m1, Ollie on OpenClaw/CherryRd).

The demo proves the things a flat memory file — or simply a bigger prompt —
**cannot** do:

| Beat | What it shows | Why it matters |
|------|---------------|----------------|
| 0 | Gateway health, all 4 tiers registered | the engine is live |
| 1 | T0 stream / T1 atoms / T3 core all return real data | tiered, distilled memory — not a log dump |
| 2 | Recall by **meaning** (semantic) *and* by keyword (lexical) | hybrid RRF retrieval beats either alone |
| 3 | **Tenant isolation** — two agents on one gateway, private stores walled off | multi-tenant by construction |
| 4 | **Shared pool** — Kukla writes, Ollie reads; private stores stay clean | agents share knowledge *on purpose* |

## Architecture

**One FALDA instance** serves both agents:

```
                 ┌──────────────────────────────────────────┐
                 │   FALDA gateway  (CherryRd :8078)         │
                 │   one store root, sqlite-vec + FTS5, RRF  │
                 └──────────────────────────────────────────┘
                    │                │                 │
        tenant "kukla"        tenant "ollie"      pool "agent-shared-demo"
        (Kukla private)       (Ollie private)     (both: readwrite)
        Hermes / m1           OpenClaw/CherryRd   opt-in shared brain
```

- Each **tenant** gets a physically separate store (`root/tenants/<tenant>/self/`).
- A **pool** is a declared shared store (`root/pools/<pool>/`) that member tenants
  route to explicitly (`pool` field on the request). Undeclared pool = error;
  isolation is the default, sharing is opt-in.
- Access modes per member: `none` | `read` | `readwrite`.

## Run it

```bash
bash falda_demo.sh
# override the gateway / tenants / pool:
FALDA_URL=http://<tailnet-aggregator>:8078 FALDA_TENANT=kukla FALDA_TENANT_B=ollie \
  FALDA_POOL=agent-shared-demo bash falda_demo.sh
```

Expected: **10 PASS / 0 FAIL**. Pure-stdlib Python driver — no `curl`/`jq` needed.

## The headline beat — cross-session recall (manual)

The automated script proves the mechanics. The beat that lands with any audience
is the **amnesia test**, which by definition needs a fresh session:

1. In a live agent session, state a distinctive fact ("the demo passphrase is *heron-42*").
2. Wait one distiller tick (the distiller promotes T0 → T1 atoms; see
   `~/.falda/distiller-<tenant>.log`).
3. Open a **brand-new** agent session (`/new`) and ask for the passphrase.
   → it answers correctly with **zero conversation history** in that session.

## Two-agent live version

`falda_demo.sh` simulates both agents by addressing two tenants over the API.
The *fully live* version has each agent plant via its **own** memory tool
(Kukla via Hermes `falda_memory_search`/write, Ollie via his OpenClaw memory
tool), then hand knowledge across via the shared pool. See
[`docs/TWO_AGENT_DEMO.md`](docs/TWO_AGENT_DEMO.md).

## API cheat-sheet (as exercised here)

| Route | Payload | Returns |
|-------|---------|---------|
| `GET /healthz` | — | `{ok, tiers}` |
| `POST /stream/add` | `{tenant, session_id, messages[]}` | T0 write |
| `POST /stream/search` | `{tenant, query, limit}` | `{messages[]}` (lexical/recency) |
| `POST /atoms/search` | `{tenant, query, limit}` | `{items[]}` (semantic, **tenant-isolated**) |
| `POST /atoms/upsert` | `{tenant, [pool], type, content}` | atom (write) |
| `POST /atoms/query` | `{tenant, [pool], query, limit}` | `{items[]}` |
| `POST /core/read` | `{tenant}` | `{content}` (T3 persona) |
| `POST /pools/declare` | `{name, members:{tenant:access}, description}` | pool decl |
| `POST /pools/grant` | `{name, tenant, access}` | pool decl |
| `POST /pools/get` | `{name}` | `{pool}` |

Access enum is `"none" | "read" | "readwrite"` (**not** `rw`/`ro`).

## Findings

See [`docs/FINDINGS.md`](docs/FINDINGS.md) for an access-enum gotcha uncovered
while building this demo (`/pools/declare` silently accepts invalid access
strings like `"rw"` → read-only fallback). Candidate issue for
`rick-stevens-ai/falda`.

## Files

- `falda_demo.sh` — the canonical 10-beat demo (Kukla).
- `alt/falda_demo_ollie.sh` — Ollie's original pure-stdlib driver, preserved.
- `docs/TWO_AGENT_DEMO.md` — fully-live two-agent runbook.
- `docs/FINDINGS.md` — isolation-route findings for the FALDA server.
