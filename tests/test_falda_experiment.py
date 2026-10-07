import json
import tempfile
import threading
import unittest
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from falda_experiment import Config, Experiment


class FakeState:
    def __init__(self, phantom_failed_write=False):
        self.private = {}
        self.pools = {}
        self.stream = {}
        self.phantom_failed_write = phantom_failed_write
        self.lock = threading.Lock()


@contextmanager
def fake_gateway(phantom_failed_write=False):
    state = FakeState(phantom_failed_write)

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_args):
            pass

        def reply(self, status, body):
            encoded = json.dumps(body, sort_keys=True).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

        def do_GET(self):
            if self.path == "/healthz":
                self.reply(200, {"ok": True, "tiers": ["T0", "T1", "T2", "T3"]})
            else:
                self.reply(404, {"error": "not_found"})

        def do_POST(self):
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length) or b"{}")
            path = self.path
            with state.lock:
                if path == "/pools/declare":
                    state.pools[payload["name"]] = {"members": dict(payload.get("members", {})), "items": []}
                    return self.reply(200, {"pool": payload})
                if path == "/pools/grant":
                    state.pools[payload["name"]]["members"][payload["tenant"]] = payload["access"]
                    return self.reply(200, {"ok": True})
                if path == "/stream/add":
                    state.stream.setdefault(payload["tenant"], []).extend(payload["messages"])
                    return self.reply(200, {"ok": True})
                if path == "/stream/search":
                    messages = state.stream.get(payload["tenant"], [])
                    query = payload["query"].lower()
                    hits = [m for m in messages if any(w in m.get("content", "").lower() for w in query.split())]
                    return self.reply(200, {"messages": hits[:payload.get("limit", 10)]})
                if path == "/core/read":
                    return self.reply(200, {"content": "Stable family persona and long-term operating principles for " + payload["tenant"]})
                if path == "/scenes/search":
                    return self.reply(200, {"items": [{"content": "A substantive project scene links agents, decisions, and outcomes."}]})
                if path == "/atoms/upsert":
                    target = state.private.setdefault(payload["tenant"], [])
                    if payload.get("pool"):
                        pool = state.pools[payload["pool"]]
                        access = pool["members"].get(payload["tenant"], "none")
                        if access != "readwrite":
                            if state.phantom_failed_write and "ATOMIC-FAIL" in payload["content"]:
                                pool["items"].append({"id": "phantom", "content": payload["content"]})
                            return self.reply(403, {"error": "forbidden"})
                        target = pool["items"]
                    item = {"id": "atom-" + str(sum(map(len, state.private.values())) + sum(len(p["items"]) for p in state.pools.values()) + 1), "content": payload["content"]}
                    if "ATOMIC-FAIL" in payload["content"]:
                        if state.phantom_failed_write:
                            target.append(item)
                        return self.reply(503, {"error": "injected"})
                    target.append(item)
                    return self.reply(200, item)
                if path in ("/atoms/query", "/atoms/search"):
                    source = state.private.get(payload["tenant"], [])
                    if payload.get("pool"):
                        pool = state.pools[payload["pool"]]
                        access = pool["members"].get(payload["tenant"], "none")
                        if access not in ("read", "readwrite"):
                            return self.reply(403, {"error": "forbidden"})
                        source = pool["items"]
                    query = payload["query"].lower()
                    # Deterministic toy semantic rule for the fixture paraphrase.
                    if "ocean-colored" in query and "morning drink" in query:
                        hits = [x for x in source if "blue ceramic" in x["content"].lower()]
                    else:
                        hits = [x for x in source if query in x["content"].lower()]
                    return self.reply(200, {"items": hits[:payload.get("limit", 10)]})
                return self.reply(404, {"error": "not_found"})

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}", state
    finally:
        server.shutdown()
        thread.join()
        server.server_close()


class HarnessUnitTests(unittest.TestCase):
    def test_run_ids_are_unique_and_manifested(self):
        with tempfile.TemporaryDirectory() as tmp:
            first = Experiment(Config(gateway="http://127.0.0.1:1", output_dir=Path(tmp)))
            second = Experiment(Config(gateway="http://127.0.0.1:1", output_dir=Path(tmp)))
            self.assertNotEqual(first.run_id, second.run_id)
            self.assertRegex(first.run_id, r"^[0-9]{8}T[0-9]{6}Z-[0-9a-f]{12}$")
            first.write_manifest()
            manifest = json.loads((first.run_dir / "manifest.json").read_text())
            self.assertEqual(manifest["run_id"], first.run_id)
            self.assertEqual(manifest["generated_ids"], [])

    def test_full_five_agent_experiment_is_deterministic_and_preserves_evidence(self):
        with tempfile.TemporaryDirectory() as tmp, fake_gateway() as (url, _state):
            experiment = Experiment(Config(gateway=url, output_dir=Path(tmp), requests_per_worker=2))
            summary = experiment.run()
            run_dir = Path(tmp) / "fixture-run"
            cli_status = Experiment(Config(gateway=url, output_dir=Path(tmp)), run_id="fixture-run").run()

            self.assertEqual(summary["status"], "pass")
            self.assertEqual(cli_status["status"], "pass")
            self.assertTrue((run_dir / "summary.json").exists())
            self.assertEqual(summary["hard_failures"], [])
            expected = {
                "seed_fixtures", "semantic_paraphrase", "lexical_distractor",
                "isolation_alpha_to_bravo", "isolation_bravo_to_alpha",
                "pool_declare", "pool_grant_readwrite", "pool_grant_read", "pool_grant_none",
                "acl_readwrite_write", "acl_read_read",
                "acl_read_write_denied", "acl_none_read_denied", "acl_none_write_denied",
                "cross_agent_shared_read", "private_nonleakage", "operation_atomicity",
                "tier_t0", "tier_t1", "tier_t2", "tier_t3", "concurrency",
            }
            self.assertTrue(expected.issubset({c["name"] for c in summary["checks"]}))
            self.assertEqual(summary["latency_ms"]["samples"], 10)
            self.assertLessEqual(summary["latency_ms"]["p50"], summary["latency_ms"]["p95"])
            self.assertTrue((experiment.run_dir / "evidence.jsonl").exists())
            evidence = [json.loads(line) for line in (experiment.run_dir / "evidence.jsonl").read_text().splitlines()]
            self.assertTrue(all("request" in row and "raw_response" in row for row in evidence))
            manifest = json.loads((experiment.run_dir / "manifest.json").read_text())
            self.assertGreaterEqual(len(manifest["generated_ids"]), 8)
            self.assertEqual(json.loads((experiment.run_dir / "summary.json").read_text()), summary)

    def test_non_2xx_write_that_persists_is_a_hard_failure(self):
        with tempfile.TemporaryDirectory() as tmp, fake_gateway(phantom_failed_write=True) as (url, _state):
            summary = Experiment(Config(gateway=url, output_dir=Path(tmp), requests_per_worker=1)).run()
            atomicity = next(c for c in summary["checks"] if c["name"] == "operation_atomicity")
            self.assertEqual(atomicity["status"], "fail")
            self.assertIn("operation_atomicity", summary["hard_failures"])
            self.assertEqual(summary["status"], "fail")


if __name__ == "__main__":
    unittest.main()
