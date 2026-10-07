# Five-agent deterministic experiment runbook

`falda_experiment.py` is the auditable companion to the short, canonical
`falda_demo.sh`. It uses only Python's standard library and targets a FALDA HTTP
gateway without modifying the server.

## Safety and prerequisites

Use five disposable tenant names. The harness creates a uniquely named pool and
uniquely tagged atoms/stream messages. FALDA's demonstrated API has no delete
route, so the run manifest records every generated pool, atom, session, and token
for manual cleanup or retention. Do not point the experiment at valued tenant
names unless retaining tagged fixtures is acceptable.

Python 3.10+ is sufficient. No package installation is needed.

## Run

```bash
FALDA_URL=http://gateway.example:8078 \
FALDA_FAMILY_TENANTS=demo-a,demo-b,demo-c,demo-d,demo-e \
./falda_family_experiment.sh
```

Equivalent direct command:

```bash
python3 falda_experiment.py \
  --gateway http://gateway.example:8078 \
  --tenants demo-a,demo-b,demo-c,demo-d,demo-e \
  --output-dir runs --concurrency 4 --requests-per-worker 3
```

Exactly five unique tenants are required. The command exits `0` only when every
supported substantive check passes. Unsupported T2 (`404`/`405`) is recorded as
`skip`; T0, T1, and T3 are still checked. Any rejected write whose unique token
can subsequently be read is an explicit **hard failure**.

## Evidence

Each invocation creates `runs/<UTC>-<random>/`:

- `manifest.json` — run ID, gateway, five tenants, generated IDs, cleanup note.
- `evidence.jsonl` — one row per HTTP exchange, including exact request, status,
  raw response body, sequence, and latency.
- `summary.json` — machine-readable pass/fail/skip checks, hard failures, and
  concurrent-load p50/p95 latency.

The checks cover seeded fixtures, semantic paraphrase versus lexical distractor,
private isolation in both directions, pool declaration and grant, `readwrite`,
`read`, and `none` ACL behavior, cross-agent shared read/write, private
nonleakage, failed-write atomicity, T0/T1/T2/T3 where supported, and a fixed
small request load across all five agents.

## Deterministic local verification

```bash
python3 -m unittest discover -s tests -v
```

The tests run a local fake HTTP gateway. They require no network or FALDA server,
and include both a clean run and an injected atomicity violation that must become
a hard failure.

## Reading the result

```bash
python3 -m json.tool runs/<run-id>/summary.json
python3 -m json.tool runs/<run-id>/manifest.json
```

Preserve the entire run directory for an audit. Raw bodies are deliberately not
normalized or discarded.
