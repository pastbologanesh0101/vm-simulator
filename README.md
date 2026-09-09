# Virtual Memory Simulator

**▶ Live demo: https://vm-simulator-playground.vercel.app** — pick a workload, frame count and policy in the browser and compare page-fault rates (runs on a Vercel Python function; code in [`web/`](web/)).

A demand-paging simulator that models the hardware/OS path for every memory
reference: **address translation** through a two-level page table and a **TLB**,
**page faults**, frame allocation, **page replacement**, and dirty-page
**write-backs** — then reports the statistics that decide real system
performance. Pure Python, no dependencies.

```
virtual address ─► [ split VPN | offset ] ─► TLB ──hit──► frame, done
                                              │miss
                                              ▼
                                    two-level page-table walk
                                              │
                                     present? ─�no─► PAGE FAULT
                                              │          │ free frame? ── yes ─► use it
                                             yes         │        no
                                              │          ▼
                                              │   replacement policy picks a victim
                                              │   dirty victim ─► disk write-back
                                              ▼          │
                                          fill TLB ◄─────┴─ page in from disk
```

## Quick start

```bash
git clone https://github.com/pastbologanesh0101/vm-simulator
cd vm-simulator
pip install -e ".[dev]"
pytest -q                                        # 22 tests

vmsim gen working-set -n 5000 -o ws.trace        # make a workload
vmsim run     ws.trace --frames 16 --policy lru  # simulate one policy
vmsim compare ws.trace --frames 16               # all policies side by side
vmsim belady                                     # demonstrate Belady's anomaly
python examples/demo.py                           # fault curve vs frame count
```

```
$ vmsim compare ws.trace --frames 16
policy       page_faults    fault_rate   disk_writes     evictions        eat_ns
fifo                 685        0.1713           395           669      270018.1
lru                  397        0.0993           110           381      126760.9
clock                398        0.0995           112           382      127510.9
random               697        0.1742           353           681      262518.4
optimal              324         0.081           102           308      106509.1

fewest faults: optimal (324)
```

## Concepts demonstrated

| Area | Where | What it shows |
|---|---|---|
| **Address translation** | `vmsim/pagetable.py` | VA split into VPN + offset from `page_size`; a real **two-level page table** (radix tree) walked on every TLB miss, with the walks counted so a deep table has a visible cost. |
| **TLB** | `vmsim/pagetable.py` | Fully-associative, LRU, configurable size; hit/miss stats; dirty-bit propagation; invalidation on eviction. A TLB hit skips the page-table walk entirely. |
| **Demand paging & faults** | `vmsim/simulator.py` | Lazy allocation (a page has no frame until first touch), the fault handler, cold vs. capacity faults, page-in disk reads. |
| **Page replacement** | `vmsim/replacement.py` | **FIFO**, **LRU** (stack algorithm), **CLOCK** / second-chance, **Random**, and **Optimal** (Belady's MIN — the offline lower bound). Each hand-verified against textbook eviction sequences. |
| **Dirty pages** | `vmsim/simulator.py` | Writes set the dirty bit; evicting a dirty page costs a disk write-back; a clean page does not. Reflected in `disk_writes`. |
| **Belady's anomaly** | `vmsim belady`, `test_simulator.py` | FIFO faulting *more* with *more* frames — reproduced on the classic `1 2 3 4 1 2 5 1 2 3 4 5` string (3 frames → 9 faults, 4 frames → 10). LRU and Optimal, being stack algorithms, never do this — also tested. |
| **Effective access time** | `Stats.effective_access_cost` | A toy EAT model (TLB 1 / memory 100 / disk 1e6 ns) so the policies' fault-rate differences translate into a single comparable number. |

## Workload models (`vmsim gen`)

- **sequential** — striding through memory; the worst case for LRU-family, the
  best for... nothing.
- **random** — uniform over a page span; locality-free baseline.
- **working-set** — ~90% of references hit a small hot set, the rest a large
  cold tail; the hot set can drift every N references to model phase changes.
  This is where LRU/CLOCK shine and FIFO/Random struggle.

## Trace format

```
R 0x1000        # read
W 4096          # write (decimal or 0x hex); marks the page dirty
R 0x1004        # comments after # are ignored
```

## What it models — and what it doesn't

**Models:** single address space, two-level page table + TLB, demand paging,
five replacement policies, dirty write-back, cold/capacity fault split, a
tunable page size and virtual-address width.

**Doesn't:** multiple processes / context switches, shared pages / copy-on-write,
page-table paging itself, prefetching, the second-chance *and* modified bits
together (NRU), memory-mapped files, or a real backing-store layout — the disk
is just a counter.

## Project layout

```
vmsim/
  pagetable.py   PTE, two-level page table, TLB
  replacement.py FIFO / LRU / Clock / Random / Optimal
  simulator.py   VirtualMemory: the translate+fault+evict loop, Stats
  trace.py       trace parsing + sequential/random/working-set generators
  cli.py         run / compare / gen / belady
examples/
  demo.py        page-fault curve vs frame count
tests/           translation / replacement (textbook sequences) / simulator
```

## License

MIT
