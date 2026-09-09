"""Print the working-set-size vs page-fault curve for each policy.

    python examples/demo.py
"""

from vmsim import trace as tr
from vmsim.simulator import compare_policies

workload = tr.working_set(6000, hot_pages=10, cold_pages=400, hot_ratio=0.85, seed=42)

print(f"{'frames':>7} | " + " | ".join(f"{p:>8}" for p in
      ("fifo", "lru", "clock", "random", "optimal")))
print("-" * 62)
for frames in (4, 6, 8, 12, 16, 24, 32, 48):
    table = compare_policies(workload, frames)
    row = " | ".join(f"{table[p]['page_faults']:>8}" for p in
                     ("fifo", "lru", "clock", "random", "optimal"))
    print(f"{frames:>7} | {row}")

print("\nNote how LRU/CLOCK track OPTIMAL closely once frames >= the hot set,")
print("while FIFO and RANDOM keep faulting on the cold tail.")
