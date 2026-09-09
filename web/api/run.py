"""Vercel serverless function: run the virtual-memory simulator.

POST {
  "mode": "run" | "compare",
  "policy": "lru", "frames": 16, "tlb": 16,
  "workload": "sequential" | "random" | "working-set",
  "n": 20000, "write_ratio": 0.3
}
-> {"ok": true, "kind": "run"|"compare"|"belady", ...}
"""

from http.server import BaseHTTPRequestHandler
import json

from vmsim import trace as tracemod
from vmsim.simulator import VirtualMemory, compare_policies

MAX_N = 60_000
POLICIES = ["fifo", "lru", "clock", "random", "optimal"]


def build_trace(workload: str, n: int, write_ratio: float):
    n = max(100, min(int(n), MAX_N))
    if workload == "sequential":
        return tracemod.sequential(n, write_ratio=write_ratio)
    if workload == "random":
        return tracemod.uniform_random(n, span_pages=512, write_ratio=write_ratio)
    return tracemod.working_set(n, hot_pages=12, cold_pages=400, hot_ratio=0.88,
                                write_ratio=write_ratio, shift_every=n // 3 or 0)


def handle(data: dict) -> dict:
    mode = data.get("mode", "run")
    frames = max(1, min(int(data.get("frames", 16)), 4096))
    tlb = max(0, min(int(data.get("tlb", 16)), 512))
    workload = data.get("workload", "working-set")
    n = int(data.get("n", 20_000))
    wr = float(data.get("write_ratio", 0.3))
    trace = build_trace(workload, n, wr)
    common = dict(page_size=4096, vaddr_bits=32, tlb_entries=tlb)

    if mode == "belady":
        seq = [1, 2, 3, 4, 1, 2, 5, 1, 2, 3, 4, 5]
        t = [(False, p * 4096) for p in seq]
        rows = []
        for f in (3, 4):
            vm = VirtualMemory(f, "fifo", tlb_entries=0)
            vm.run(t)
            rows.append({"frames": f, "page_faults": vm.stats.page_faults})
        return {"ok": True, "kind": "belady", "rows": rows,
                "note": "FIFO: more frames, MORE faults on this reference string."}

    if mode == "compare":
        table = compare_policies(trace, frames, policies=POLICIES, **common)
        best = min(table, key=lambda p: table[p]["page_faults"])
        return {"ok": True, "kind": "compare", "frames": frames,
                "workload": workload, "requests": len(trace),
                "table": table, "best": best}

    policy = data.get("policy", "lru")
    if policy not in POLICIES:
        return {"ok": False, "text": f"unknown policy {policy!r}"}
    vm = VirtualMemory(frames, policy, **common)
    vm.run(trace)
    return {"ok": True, "kind": "run", "policy": policy, "frames": frames,
            "workload": workload, "requests": len(trace),
            "stats": vm.stats.as_dict()}


class handler(BaseHTTPRequestHandler):
    def _send(self, code, obj):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):  # noqa: N802
        self._send(204, {})

    def do_POST(self):  # noqa: N802
        try:
            n = int(self.headers.get("Content-Length") or 0)
            data = json.loads(self.rfile.read(n) or b"{}")
            self._send(200, handle(data))
        except Exception as e:  # noqa: BLE001
            self._send(200, {"ok": False, "text": f"{type(e).__name__}: {e}"})

    def do_GET(self):  # noqa: N802
        self._send(200, {"ok": True, "text": "POST simulation params here"})
