"""``vmsim`` command line.

    vmsim run     trace.txt --frames 16 --policy lru
    vmsim compare trace.txt --frames 16
    vmsim gen     working-set -n 5000 -o trace.txt
    vmsim belady                       # demonstrate Belady's anomaly
"""

from __future__ import annotations

import argparse
import sys

from .simulator import VirtualMemory, compare_policies
from .trace import GENERATORS, format_trace, parse_trace


def _load(path: str):
    stream = sys.stdin if path == "-" else open(path)
    with stream as f:
        return parse_trace(f)


def cmd_run(ns) -> int:
    trace = _load(ns.trace)
    vm = VirtualMemory(ns.frames, ns.policy, page_size=ns.page_size,
                       vaddr_bits=ns.vaddr_bits, tlb_entries=ns.tlb)
    vm.run(trace)
    width = max(len(k) for k in vm.stats.as_dict())
    for k, v in vm.stats.as_dict().items():
        print(f"{k:<{width}}  {v}")
    return 0


def cmd_compare(ns) -> int:
    trace = _load(ns.trace)
    table = compare_policies(trace, ns.frames, page_size=ns.page_size,
                             vaddr_bits=ns.vaddr_bits, tlb_entries=ns.tlb)
    cols = ["page_faults", "fault_rate", "disk_writes", "evictions", "eat_ns"]
    print(f"{'policy':<10}" + "".join(f"{c:>14}" for c in cols))
    for name, st in table.items():
        print(f"{name:<10}" + "".join(f"{st[c]:>14}" for c in cols))
    best = min(table, key=lambda n: table[n]["page_faults"])
    print(f"\nfewest faults: {best} ({table[best]['page_faults']})")
    return 0


def cmd_gen(ns) -> int:
    gen = GENERATORS[ns.kind]
    kwargs = {"n": ns.n}
    if ns.write_ratio is not None:
        kwargs["write_ratio"] = ns.write_ratio
    refs = gen(**kwargs)
    text = format_trace(refs)
    if ns.output and ns.output != "-":
        open(ns.output, "w").write(text)
        print(f"wrote {len(refs)} references to {ns.output}", file=sys.stderr)
    else:
        sys.stdout.write(text)
    return 0


def cmd_belady(ns) -> int:
    """FIFO can fault *more* with more frames. Classic sequence: 1 2 3 4 1 2 5 1 2 3 4 5."""
    seq = [1, 2, 3, 4, 1, 2, 5, 1, 2, 3, 4, 5]
    ps = 4096
    trace = [(False, p * ps) for p in seq]
    print("Belady's anomaly (FIFO):")
    for frames in (3, 4):
        vm = VirtualMemory(frames, "fifo", tlb_entries=0)
        vm.run(trace)
        print(f"  {frames} frames -> {vm.stats.page_faults} page faults")
    print("more frames, more faults — that's the anomaly. LRU/Optimal never do this.")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="vmsim")
    sub = p.add_subparsers(dest="cmd", required=True)

    def add_common(s):
        s.add_argument("--frames", type=int, default=16)
        s.add_argument("--page-size", type=int, default=4096)
        s.add_argument("--vaddr-bits", type=int, default=32)
        s.add_argument("--tlb", type=int, default=16, help="TLB entries (0 disables)")

    s = sub.add_parser("run"); s.add_argument("trace")
    s.add_argument("--policy", default="lru")
    add_common(s); s.set_defaults(func=cmd_run)

    s = sub.add_parser("compare"); s.add_argument("trace")
    add_common(s); s.set_defaults(func=cmd_compare)

    s = sub.add_parser("gen")
    s.add_argument("kind", choices=list(GENERATORS))
    s.add_argument("-n", type=int, default=2000)
    s.add_argument("--write-ratio", type=float, default=None)
    s.add_argument("-o", "--output", default="-")
    s.set_defaults(func=cmd_gen)

    s = sub.add_parser("belady"); s.set_defaults(func=cmd_belady)
    return p


def main(argv=None) -> int:
    ns = build_parser().parse_args(argv)
    return ns.func(ns)


if __name__ == "__main__":
    raise SystemExit(main())
