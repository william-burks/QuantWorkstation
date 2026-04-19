# ROADMAP — Deferred Capabilities

Capabilities we intend to build but have not scheduled yet. Items here are **not in
the active backlog** (`epics/INDEX.md`) and have **no code in the tree**.
When work begins, create an epic/story and move the item to `BACKLOG_ALIGNMENT.md`.

Each entry records what was removed, when, and the commit SHA so the previous
implementation can be recovered via `git show <sha>:<path>` if needed as a starting
point.

---

## Live Trading — IBKR Futures

**Status:** Deferred. Paper + research-only until a champion passes OOS validation
and Will decides to go live.

**What it would do:** Connect to IB Gateway (paper: port 4002, live: port 4001) and
execute Order objects produced by `execution/oms.py::OMS.rebalance()`. Handles
contract qualification (front-month), position queries, and account state.

**Why removed:** Zero callers. No champion has cleared OOS to the point where live
execution matters. Keeping the class in the tree implied readiness that did not
exist.

**Dependencies preserved:**
- `ib_insync` stays in `pyproject.toml` — `data/collectors/ibkr_futures.py` uses it
  for futures bar ingestion.
- `ibkr_host` / `ibkr_port` / `ibkr_client_id` stay in `data/config.py` for the
  collector.

**Reference implementation:** `execution/brokers/ibkr.py` — removed in the Phase 3
audit. Last commit containing the file: run `git log --all -- execution/brokers/ibkr.py`
to locate, then `git show <sha>:execution/brokers/ibkr.py` to recover.

**Scope when revived:**
- Resurrect `IBKRBroker` class mirroring the `AlpacaBroker` interface in
  `execution/brokers/alpaca.py`
- Wire into `execution/oms.py` as a broker choice
- Integration tests against IB Gateway paper account
- Update `execution/types.py` docstring to mention `IBKRBroker` again

---

## How this doc is maintained

- **Add an entry** when code is removed because a capability is not yet needed.
- **Remove an entry** when a story covering the work enters `READY` in
  `BACKLOG_ALIGNMENT.md`.
- **Never** park active scaffolding here — if code is in the tree and half-shipped,
  it belongs in a story, not a roadmap note.
