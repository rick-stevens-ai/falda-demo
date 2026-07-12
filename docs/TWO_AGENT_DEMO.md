# Two-agent live FALDA demo

`falda_demo.sh` simulates both agents by addressing two tenants over the HTTP
API from one host. This runbook is the **fully live** version: each agent plants
memory through its *own* memory tool, then hands knowledge to the other via the
shared pool. This is the version to run in front of an audience when you want to
show real agents, not curl.

## Cast

- **Kukla** — Hermes agent on `m1-mac-mini`. FALDA tenant `kukla`.
  Writes via its Hermes FALDA provider; recalls via `falda_memory_search`.
- **Ollie** — OpenClaw agent on `CherryRd`. FALDA tenant `ollie`.
  Writes/recalls via its own OpenClaw memory tool.
- **Shared pool** — `agent-shared-demo`, both members `readwrite`.

Both talk to the **same** gateway: `http://<tailnet-aggregator>:8078`.

## One-time setup — declare the shared pool

```bash
BASE=http://<tailnet-aggregator>:8078
curl -s -X POST $BASE/pools/declare -H 'Content-Type: application/json' -d '{
  "name":"agent-shared-demo",
  "members":{"kukla":"readwrite","ollie":"readwrite"},
  "description":"Shared cross-agent memory demo pool (Kukla+Ollie)"
}'
```

(Access enum is `none|read|readwrite` — do NOT use `rw`/`ro`.)

## Beat A — private memory is private

1. In Kukla's session: *"Remember for the demo: my private token is FALCON-9."*
   (Kukla writes to tenant `kukla`, no pool.)
2. In Ollie's session: *"What is Kukla's private demo token?"*
   → Ollie recalls from tenant `ollie` and finds **nothing**. Private stays private.

## Beat B — deliberate sharing via the pool

3. In Kukla's session: *"Put this in the shared pool for Ollie: the joint
   experiment ID is LUCID-T1-RNAseq-846GB on Eagle."*
   (Kukla writes with `pool: agent-shared-demo`.)
4. Wait ~1 distiller tick.
5. In Ollie's session: *"Check the shared pool — what joint experiment did Kukla
   leave for me?"*
   → Ollie reads the pool and returns **LUCID-T1-RNAseq-846GB on Eagle**.
6. (Optional, reverse) Ollie writes a result back into the pool; Kukla reads it.
   Shows bidirectional cross-agent memory hand-off.

## Beat C — cross-session persistence (the amnesia test)

7. End Kukla's session entirely (`/new`).
8. Start a fresh Kukla session and ask about the shared experiment ID.
   → still recalled — memory outlived the conversation.

## What the audience should take away

- Two independent agents, two stacks (Hermes + OpenClaw), **one memory brain**.
- Each keeps a **private** store; they share **only** what they choose, through a
  declared pool with explicit access control.
- Memory is durable across sessions and recalled by meaning, not keyword.

## Verifying from the CLI (witness lines)

```bash
# what's in the shared pool right now:
curl -s -X POST http://<tailnet-aggregator>:8078/atoms/query -H 'Content-Type: application/json' \
  -d '{"tenant":"ollie","pool":"agent-shared-demo","query":"joint experiment","limit":5}'
```
