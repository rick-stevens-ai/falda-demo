#!/usr/bin/env python3
"""Deterministic, evidence-preserving FALDA five-agent experiment harness."""
from __future__ import annotations

import argparse
import json
import math
import threading
import time
import urllib.error
import urllib.request
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class Config:
    gateway: str
    output_dir: Path = Path("runs")
    tenants: tuple[str, ...] = ("alpha", "bravo", "charlie", "delta", "echo")
    pool_prefix: str = "falda-family"
    concurrency: int = 4
    requests_per_worker: int = 3
    timeout: float = 12.0


@dataclass
class HttpResult:
    status: int
    body: Any
    raw: str
    latency_ms: float


@dataclass
class Experiment:
    config: Config
    run_id: str = field(default_factory=lambda: datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ-") + uuid.uuid4().hex[:12])
    generated_ids: list[dict[str, str]] = field(default_factory=list)
    checks: list[dict[str, Any]] = field(default_factory=list)
    hard_failures: list[str] = field(default_factory=list)
    _evidence_lock: threading.Lock = field(default_factory=threading.Lock, repr=False)
    _sequence: int = 0

    @property
    def run_dir(self) -> Path:
        return self.config.output_dir / self.run_id

    def generated(self, kind: str, value: str) -> str:
        self.generated_ids.append({"kind": kind, "id": value})
        return value

    def token(self, label: str) -> str:
        return self.generated("token", f"{self.run_id}-{label}")

    def pool_name(self) -> str:
        # Pool IDs are limited to 64 lowercase [a-z0-9_-] characters.
        compact = self.run_id.lower().replace("t", "").replace("z", "")
        return self.generated("pool", f"{self.config.pool_prefix}-{compact}"[:64])

    def write_manifest(self) -> Path:
        self.run_dir.mkdir(parents=True, exist_ok=True)
        path = self.run_dir / "manifest.json"
        path.write_text(json.dumps({
            "schema_version": 1,
            "run_id": self.run_id,
            "gateway": self.config.gateway,
            "tenants": list(self.config.tenants),
            "generated_ids": self.generated_ids,
            "cleanup": {"supported": False, "action": "All generated IDs are listed here for manual cleanup."},
        }, indent=2, sort_keys=True) + "\n")
        return path

    def call(self, method: str, path: str, payload: dict[str, Any] | None = None) -> HttpResult:
        data = None if payload is None else json.dumps(payload, sort_keys=True).encode()
        request = urllib.request.Request(
            self.config.gateway.rstrip("/") + path, data=data, method=method,
            headers={"Content-Type": "application/json", "X-FALDA-Experiment": self.run_id},
        )
        started = time.perf_counter()
        try:
            with urllib.request.urlopen(request, timeout=self.config.timeout) as response:
                status, raw = response.status, response.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as error:
            status, raw = error.code, error.read().decode("utf-8", "replace")
        except Exception as error:  # Preserve transport failures as evidence.
            status, raw = 0, json.dumps({"error": f"{type(error).__name__}: {error}"})
        latency = (time.perf_counter() - started) * 1000
        try:
            body = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            body = None
        with self._evidence_lock:
            self._sequence += 1
            record = {
                "sequence": self._sequence, "method": method, "path": path,
                "request": payload, "status": status, "raw_response": raw,
                "latency_ms": round(latency, 3),
            }
            self.run_dir.mkdir(parents=True, exist_ok=True)
            with (self.run_dir / "evidence.jsonl").open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(record, sort_keys=True) + "\n")
        return HttpResult(status, body, raw, latency)

    @staticmethod
    def items(result: HttpResult, key: str = "items") -> list[dict[str, Any]]:
        return result.body.get(key, []) if isinstance(result.body, dict) else []

    @staticmethod
    def contains(result: HttpResult, token: str, key: str = "items") -> bool:
        return any(token in str(item.get("content", "")) for item in Experiment.items(result, key))

    def check(self, name: str, passed: bool | None, detail: str = "", hard: bool = False) -> None:
        status = "skip" if passed is None else ("pass" if passed else "fail")
        self.checks.append({"name": name, "status": status, "detail": detail})
        if hard and passed is False:
            self.hard_failures.append(name)

    def upsert(self, tenant: str, content: str, pool: str | None = None) -> HttpResult:
        payload: dict[str, Any] = {"tenant": tenant, "type": "episodic", "content": content, "text": content}
        if pool:
            payload["pool"] = pool
        result = self.call("POST", "/atoms/upsert", payload)
        if 200 <= result.status < 300 and isinstance(result.body, dict) and result.body.get("id"):
            self.generated("atom", str(result.body["id"]))
        return result

    def run(self) -> dict[str, Any]:
        if len(self.config.tenants) != 5:
            raise ValueError("the family demo requires exactly five unique tenants")
        if len(set(self.config.tenants)) != 5:
            raise ValueError("tenant names must be unique")
        self.run_dir.mkdir(parents=True, exist_ok=False)
        alpha, bravo, charlie, delta, echo = self.config.tenants
        pool = self.pool_name()

        health = self.call("GET", "/healthz")
        health_ok = health.status == 200 and isinstance(health.body, dict) and bool(health.body.get("ok"))

        # Seed deterministic T0 and T1 fixtures. Semantic target and lexical distractor
        # share a topic but only the target satisfies the paraphrase.
        session = self.generated("session", f"session-{self.run_id}")
        lexical = self.token("lexical-lantern")
        target = self.token("semantic-target")
        distractor = self.token("semantic-distractor")
        t0 = self.call("POST", "/stream/add", {"tenant": alpha, "session_id": session, "messages": [
            {"role": "user", "content": f"Exact lexical beacon {lexical}"}
        ]})
        target_write = self.upsert(alpha, f"{target}: the blue ceramic mug holds the morning coffee")
        distractor_write = self.upsert(alpha, f"{distractor}: ocean-colored reports discuss quarterly tea exports")
        self.check("seed_fixtures", t0.status < 300 and target_write.status < 300 and distractor_write.status < 300)

        semantic = self.call("POST", "/atoms/search", {"tenant": alpha, "query": "which ocean-colored cup holds the morning drink", "limit": 5})
        self.check("semantic_paraphrase", self.contains(semantic, target), "target recovered by meaning")
        semantic_items = self.items(semantic)
        target_rank = next((i + 1 for i, item in enumerate(semantic_items) if target in item.get("content", "")), None)
        distractor_rank = next((i + 1 for i, item in enumerate(semantic_items) if distractor in item.get("content", "")), None)
        self.check("semantic_target_ranks_ahead_of_distractor",
                   target_rank is not None and (distractor_rank is None or target_rank < distractor_rank),
                   f"target_rank={target_rank}; distractor_rank={distractor_rank}")

        lexical_result = self.call("POST", "/stream/search", {"tenant": alpha, "query": lexical, "limit": 5})
        self.check("tier_t0", self.contains(lexical_result, lexical, "messages"), "seeded raw turn returned")
        self.check("tier_t1", self.contains(semantic, target), "seeded typed atom returned")

        # Seed and round-trip substantive, run-scoped T2/T3 fixtures. This avoids
        # claiming tier coverage from unrelated pre-existing production content.
        scene_path = self.generated("scene", f"family-demo/{self.run_id}.md")
        scene_text = f"FALDA family scene {self.run_id}: five keepers reconstruct a synthetic instrument incident."
        scene_write = self.call("POST", "/scenes/write", {"tenant": alpha, "path": scene_path, "content": scene_text})
        scene_read = self.call("POST", "/scenes/read", {"tenant": alpha, "path": scene_path})
        scene_content = scene_read.body.get("content", "") if isinstance(scene_read.body, dict) else ""
        self.check("tier_t2", scene_write.status == 200 and scene_read.status == 200 and scene_text == scene_content,
                   "run-scoped scene round-tripped")

        core_before = self.call("POST", "/core/read", {"tenant": echo})
        old_core = core_before.body.get("content", "") if isinstance(core_before.body, dict) else ""
        core_text = f"FALDA family core {self.run_id}: preserve evidence, identity, and explicit sharing boundaries."
        core_write = self.call("POST", "/core/write", {"tenant": echo, "content": core_text})
        core_read = self.call("POST", "/core/read", {"tenant": echo})
        core_content = core_read.body.get("content", "") if isinstance(core_read.body, dict) else ""
        self.check("tier_t3", core_write.status == 200 and core_read.status == 200 and core_content == core_text,
                   "run-scoped core round-tripped")
        # Restore any prior core immediately; a disposable tenant normally had none.
        self.call("POST", "/core/write", {"tenant": echo, "content": old_core})
        self.check("gateway_health", health_ok)

        # Private isolation in both directions.
        a_secret, b_secret = self.token("private-alpha"), self.token("private-bravo")
        aw, bw = self.upsert(alpha, f"private {a_secret}"), self.upsert(bravo, f"private {b_secret}")
        a_from_b = self.call("POST", "/atoms/search", {"tenant": bravo, "query": a_secret, "limit": 5})
        b_from_a = self.call("POST", "/atoms/search", {"tenant": alpha, "query": b_secret, "limit": 5})
        self.check("isolation_alpha_to_bravo", aw.status < 300 and not self.contains(a_from_b, a_secret), hard=True)
        self.check("isolation_bravo_to_alpha", bw.status < 300 and not self.contains(b_from_a, b_secret), hard=True)

        members = {alpha: "readwrite", bravo: "read", charlie: "none", delta: "readwrite", echo: "readwrite"}
        declared = self.call("POST", "/pools/declare", {"name": pool, "members": members, "description": f"five-agent experiment {self.run_id}"})
        self.check("pool_declare", declared.status < 300)
        # Exercise grant independently for every ACL mode, preserving final intent.
        for tenant, access in ((alpha, "readwrite"), (bravo, "read"), (charlie, "none")):
            granted = self.call("POST", "/pools/grant", {"name": pool, "tenant": tenant, "access": access})
            self.check(f"pool_grant_{access}", granted.status < 300)

        shared = self.token("shared-alpha-delta")
        shared_write = self.upsert(alpha, f"shared fact {shared}", pool)
        shared_read = self.call("POST", "/atoms/query", {"tenant": delta, "pool": pool, "query": shared, "limit": 5})
        self.check("acl_readwrite_write", shared_write.status < 300)
        self.check("cross_agent_shared_read", self.contains(shared_read, shared))
        read_only = self.call("POST", "/atoms/query", {"tenant": bravo, "pool": pool, "query": shared, "limit": 5})
        self.check("acl_read_read", self.contains(read_only, shared))
        denied_read_write = self.upsert(bravo, f"denied read-only write {self.token('denied-read-write')}", pool)
        self.check("acl_read_write_denied", not 200 <= denied_read_write.status < 300)
        denied_none_read = self.call("POST", "/atoms/query", {"tenant": charlie, "pool": pool, "query": shared, "limit": 5})
        self.check("acl_none_read_denied", not 200 <= denied_none_read.status < 300)
        denied_none_write = self.upsert(charlie, f"denied none write {self.token('denied-none-write')}", pool)
        self.check("acl_none_write_denied", not 200 <= denied_none_write.status < 300)
        private_probe = self.call("POST", "/atoms/search", {"tenant": delta, "query": shared, "limit": 5})
        self.check("private_nonleakage", not self.contains(private_probe, shared), hard=True)

        # Atomicity invariant: a rejected write MUST leave no token behind.
        atomic = self.token("ATOMIC-FAIL")
        rejected = self.upsert(bravo, f"ATOMIC-FAIL rejected payload {atomic}", pool)
        persisted = self.call("POST", "/atoms/query", {"tenant": alpha, "pool": pool, "query": atomic, "limit": 5})
        atomic_ok = not 200 <= rejected.status < 300 and not self.contains(persisted, atomic)
        self.check("operation_atomicity", atomic_ok, f"write_status={rejected.status}; persisted={self.contains(persisted, atomic)}", hard=True)

        # Small fixed load: exactly workers * requests per worker observations.
        def load(worker: int, request_number: int) -> float:
            result = self.call("POST", "/atoms/search", {"tenant": self.config.tenants[worker], "query": target, "limit": 1, "probe": request_number})
            if result.status != 200:
                raise RuntimeError(f"load request failed with {result.status}")
            return result.latency_ms

        jobs = [(worker, request) for worker in range(len(self.config.tenants)) for request in range(self.config.requests_per_worker)]
        latencies: list[float] = []
        load_error = ""
        try:
            with ThreadPoolExecutor(max_workers=self.config.concurrency) as executor:
                latencies = list(executor.map(lambda pair: load(*pair), jobs))
        except Exception as error:
            load_error = str(error)
        self.check("concurrency", len(latencies) == len(jobs), load_error or f"{len(latencies)} requests")
        ordered = sorted(latencies)
        percentile = lambda p: round(ordered[max(0, math.ceil(p * len(ordered)) - 1)], 3) if ordered else None
        latency_summary = {"samples": len(ordered), "p50": percentile(.50), "p95": percentile(.95)}

        failed = [check["name"] for check in self.checks if check["status"] == "fail"]
        summary = {
            "schema_version": 1, "run_id": self.run_id,
            "status": "pass" if not failed else "fail", "checks": self.checks,
            "failed_checks": failed, "hard_failures": self.hard_failures,
            "latency_ms": latency_summary,
        }
        self.write_manifest()
        (self.run_dir / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
        return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gateway", required=True)
    parser.add_argument("--output-dir", type=Path, default=Path("runs"))
    parser.add_argument("--tenants", default="alpha,bravo,charlie,delta,echo")
    parser.add_argument("--pool-prefix", default="falda-family")
    parser.add_argument("--concurrency", type=int, default=4)
    parser.add_argument("--requests-per-worker", type=int, default=3)
    parser.add_argument("--timeout", type=float, default=12.0)
    args = parser.parse_args(argv)
    config = Config(
        gateway=args.gateway.rstrip("/"), output_dir=args.output_dir,
        tenants=tuple(part.strip() for part in args.tenants.split(",")),
        pool_prefix=args.pool_prefix, concurrency=args.concurrency,
        requests_per_worker=args.requests_per_worker, timeout=args.timeout,
    )
    experiment = Experiment(config)
    summary = experiment.run()
    print(json.dumps({"run_dir": str(experiment.run_dir), **summary}, sort_keys=True))
    return 0 if summary["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
