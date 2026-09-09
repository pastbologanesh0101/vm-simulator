# VM Simulator Playground (web)

The browser demo behind **https://vm-simulator-playground.vercel.app**.

- `index.html` — static UI: workload / frames / TLB / reference-count controls,
  "run one", "compare all", "Belady's anomaly".
- `api/run.py` — a Vercel Python serverless function. `POST {mode, ...}` runs
  the simulator and returns the stats (references capped at 60k).
- `vmsim/` — a vendored snapshot of the package (kept in sync with the repo
  root), so the function has no install step.

Deploy: `cd web && vercel deploy --prod`.
