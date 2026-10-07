# FALDA Family Demo: “The Five Keepers and the Vanished Experiment”

## Goal

Demonstrate, with retained evidence rather than narration alone, that five independent family agents can keep private memories, deliberately contribute fragments to a shared pool, reconstruct a composite scientific incident by semantic recall, retain it across a gateway restart and fresh agent session, and reject unauthorized access.

## Cast and non-overlapping lanes

- **Ikto** — conductor, harness owner, integration, evidence manifest, final report/deck.
- **Yéil** — independent semantic/lexical retrieval benchmark and second-method validation.
- **Tsisdu** — independent ACL, isolation, and negative-control validation.
- **Kukla** — m1/Hermes live participant; plants and recalls through the real agent/provider path; fresh-session amnesia test.
- **Ollie** — CherryRd/OpenClaw live participant and FALDA owner; production repair/deploy, pool witness, restart-survival witness.

## Story

A fictional instrument event has been split across five keepers. No agent has the complete record.

Run-scoped token: `WEB-<UTC>-<random>`.

Fragments use synthetic, non-sensitive data:

1. Ikto: instrument = **AURORA-SPECTROMETER-7**
2. Yéil: anomaly = **a violet transient appeared after the third calibration pulse**
3. Tsisdu: environment = **cryostat temperature was 4.18 K**
4. Kukla: decision = **repeat with detector gain reduced by 6 dB**
5. Ollie: location = **Eagle project archive, run shelf R-17**

Each agent first plants a distinct private control token. Other agents must not see it. Each then contributes one fragment to a declared shared pool. A sixth “synthesis” memory joins the five fragments into a complete incident record. The query never repeats the planted nouns verbatim: “What happened during the cold optical instrument run, what corrective action was chosen, and where is its record?”

## Acceptance gates

1. Health: gateway reports stream/atoms/scenes/core and pools.
2. Atomicity: any non-2xx write leaves no token behind; a successful write returns 2xx and persists exactly once.
3. Private isolation: every private token is visible to its owner and absent for all four peers.
4. ACL: non-member denied; read-only member can read but cannot write; identity-spoof attempt is clamped by the authenticated proxy.
5. Shared exchange: every keeper’s fragment is visible to every authorized pool member.
6. Semantic recall: paraphrase query retrieves the expected synthesis without relying on exact marker terms.
7. Lexical control: exact unique token retrieves its record; distractor query does not retrieve it.
8. Tier checks: substantive T0, T1, T2, and T3 records are written/read for the run, not merely pre-existing records.
9. Restart survival: after gateway restart, all run records remain retrievable and identities match.
10. Fresh-session amnesia: a newly opened agent session recalls the synthesis without receiving prior chat transcript.
11. Concurrency: bounded simultaneous writes complete without loss or duplicate IDs; report p50/p95 latency and failures.
12. Evidence: each action records UTC timestamp, actor, host, route/tool, request hash, status, latency, returned IDs, and response hash. Raw responses are retained.

## Experimental sequence

### Act I — Five locked boxes

Each member writes a private token via their own agent/provider path. The harness runs the 5×5 private-read matrix. Expected diagonal green, off-diagonal empty.

### Act II — The shared web

An authenticated operator declares one run-scoped pool and grants members. Each family member writes one fragment through its own path. The harness records all five returned IDs and verifies cross-member visibility.

### Act III — Recall without the words

A synthesis atom contains the complete event. Each agent gets a different paraphrase query. Yéil runs a blinded query set and computes Recall@1, MRR, distractor false-positive rate, p50 and p95 latency. Expected-token mappings are kept outside query inputs.

### Act IV — Cut the thread

Ollie performs a controlled gateway restart after recording pre-restart hashes/counts. The harness reconnects, verifies hostname/service identity, then re-runs exact and semantic recall. A fresh Kukla session answers the incident question without prior chat context.

### Act V — The trickster tests the locks

Tsisdu tests missing token, wrong token, identity spoof, unauthorized pool, read-only write, malformed JSON, oversized body, and unsupported route. Production direct :8078 is explicitly classified as trusted-network only; authenticated identity claims are made only through the proxy.

### Finale — Family reconstruction

All five agents independently state their fragment and the synthesized answer. Ikto compares them to the sealed expectation file and emits the signed/hash manifest. No self-report counts as evidence without matching stored record and raw response.

## Retained artifact tree

```
evidence/runs/<run-id>/
  manifest.json
  environment.json
  requests.jsonl
  results.json
  latency.csv
  private-matrix.csv
  shared-matrix.csv
  retrieval-cases.json
  retrieval-results.jsonl
  restart-before.json
  restart-after.json
  family/
    ikto.json
    yeil.json
    tsisdu.json
    kukla.json
    ollie.json
  logs/
  SHA256SUMS
```

## Abort rules

- Do not proceed to audience rehearsal if semantic recall, atomicity, private isolation, or proxy identity-clamping fails.
- Do not claim five-member execution if a member is unavailable; label the run 4/5 and preserve the missing lane as unavailable, never simulated.
- Do not restart production until the owner confirms no conflicting work and a rollback copy exists.
- Report/deck writing begins only after the final experiment manifest is closed.
