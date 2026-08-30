# Sandbox & Security

This is a working Phase-1 implementation of your role: a hardened Docker
sandbox for executing untrusted, AI-generated Python, plus the contract
your teammate (Member 1, Agent/Orchestration) will build against.

Everything below has already been run and passes (5/5 mock+contract
tests). You just need to add Docker to run the real security tests.

---

## 0. Tech stack (this module only)

| Layer | Choice | Why |
|---|---|---|
| Language | Python 3.11+ | matches the rest of the backend |
| Schema/contract | Pydantic v2 | typed, matches everyone else's contracts |
| Execution engine | Docker (via `docker-py` SDK) | mature isolation primitives, team already chose it |
| Testing | pytest + pytest-asyncio | async-native, matches `async def execute()` |
| Sandbox image | `python:3.11-slim` + pandas/numpy/openpyxl | minimal, matches Scenario A/B needs |

You do **not** need FastAPI, Next.js, Qdrant, or any LLM for this phase —
this module is self-contained and only talks to Member 1 through the
`SandboxService` interface.

---

## 1. Environment setup (do this once)

You said you're not sure about your environment — here's the most
reliable path for each OS.

### Linux (native) — simplest
```bash
# Docker Engine
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER
newgrp docker          # or log out/in
docker run hello-world # should succeed with no sudo
```

### Windows
Install **Docker Desktop with WSL2 backend**:
1. Install WSL2: `wsl --install` (PowerShell, as Administrator), then reboot.
2. Install Ubuntu from the Microsoft Store.
3. Install [Docker Desktop](https://www.docker.com/products/docker-desktop/), enable "Use the WSL2 based engine" in Settings, and enable integration with your Ubuntu distro.
4. Do all your work (clone the repo, run commands) **inside the WSL2 Ubuntu terminal**, not PowerShell — this matters for file permission behavior in the sandbox.

### Mac (Intel or Apple Silicon)
Install [Docker Desktop for Mac](https://www.docker.com/products/docker-desktop/). Everything else below works identically.

### Verify before continuing
```bash
docker --version
docker info        # must succeed without errors
python3 --version  # need 3.11+
```

---

## 2. What's in this repo

```
sovereign-sandbox/
├── backend/
│   ├── app/
│   │   ├── core/
│   │   │   ├── schemas/
│   │   │   │   ├── common.py      # ToolResult, FileRef, Artifact — SHARED with whole team
│   │   │   │   └── sandbox.py     # SandboxRequest/Result — the contract Member 1 codes against
│   │   │   └── interfaces/
│   │   │       └── sandbox.py     # SandboxService Protocol
│   │   ├── sandbox/
│   │   │   ├── mock.py            # give this to Member 1 TODAY
│   │   │   ├── service.py         # DockerSandboxService — the real thing
│   │   │   ├── docker_runner.py   # low-level docker-py calls (only file that imports docker)
│   │   │   └── workspace.py       # per-job temp dir management
│   │   ├── security/
│   │   │   └── policy.py          # every hard limit, in ONE place
│   │   └── telemetry/
│   │       └── audit.py           # structured JSON audit log per execution
│   ├── tests/
│   │   ├── unit/                  # no Docker needed
│   │   ├── contract/              # run against BOTH mock and real
│   │   └── security/              # the attack matrix — needs Docker
│   ├── sandbox_test.py            # standalone demo (mock or --real)
│   ├── requirements.txt
│   └── pytest.ini
├── docker/
│   └── sandbox-image/
│       └── Dockerfile             # the hardened image code runs inside
└── setup.sh                       # one command to build + test everything
```

---

## 3. Run it right now (no Docker needed)

```bash
cd sovereign-sandbox/backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

python3 sandbox_test.py
```

You should see 4 test cases run against the **mock** sandbox: normal
code succeeds, network attempts are blocked, timeouts fire — all
instantly, no Docker.

**This is what you hand to Member 1 today.** They can start writing
LangGraph tool calls against `SandboxService` right now:

```python
from app.sandbox.mock import MockSandboxService
from app.core.schemas.sandbox import SandboxRequest

sandbox = MockSandboxService()
result = await sandbox.execute(SandboxRequest(code="print(2+2)"))
```

---

## 4. Run it for real (once Docker is installed)

```bash
cd sovereign-sandbox
chmod +x setup.sh
./setup.sh
```

This will: build the sandbox image, run the mock tests, run the real
contract test, run the **full security attack matrix** (network
block, filesystem block, timeout, memory bomb, fork bomb), and run
the demo script against real Docker.

If everything passes, you'll see:
```
All checks passed. Your sandbox is ready to hand to Member 1.
```

If a step fails, fix it before moving on — don't let the Agent depend
on a sandbox that hasn't passed its own attack tests.

### Manual equivalent (if you want to run steps yourself)
```bash
docker build -t sovereign-sandbox-runtime:latest docker/sandbox-image/
cd backend
pytest tests/security -v        # the attack matrix
python3 sandbox_test.py --real  # real end-to-end demo
```

---

## 5. How this integrates with the rest of the team

This is the whole point of the contract-first approach: **integration
is composition, not rewriting.**

### With Member 1 (Agent)
They only ever import `SandboxService` (the interface) and
`SandboxRequest`/`SandboxResult` (the schemas). Never `docker_runner.py`
or `DockerSandboxService` directly inside agent code.

```python
# In Member 1's app composition (e.g. app/main.py):
from app.core.interfaces.sandbox import SandboxService

# During their early development:
sandbox: SandboxService = MockSandboxService()

# Once you say "ready":
sandbox: SandboxService = DockerSandboxService()

# LangGraph tool node stays IDENTICAL either way:
async def code_execution_tool(state):
    result = await sandbox.execute(SandboxRequest(code=state["generated_code"]))
    return {"execution_result": result}
```

### With Member 5 (Platform/UI)
Don't send them Docker internals. Send them events built from
`SandboxResult`:
```python
{
  "type": "sandbox.completed",
  "job_id": result.job_id,
  "status": result.status,
  "data": {"duration_ms": result.duration_ms}
}
{
  "type": "security.status",
  "data": result.security.model_dump()
}
{
  "type": "network.status",
  "data": result.network.model_dump()
}
```
This is exactly what powers their "🟢 Network isolated / 🟢 Filesystem
restricted" dashboard without them knowing anything about Docker.

### With Member 3 (Coding model)
No direct dependency — their coding model output (a string of Python)
is exactly what `SandboxRequest.code` expects. Member 1's agent is the
glue between them.

---

## 6. What's deliberately NOT in Phase 1

Per your scope choice, this build stops at the hardened Docker
sandbox. Coming next once this is solid and merged:

1. **FastAPI wrapper** — expose `POST /sandbox/execute` so it can run
   as its own service instead of an in-process import (needed once
   Member 5's FastAPI backend calls it over the network).
2. **Host firewall (iptables)** — second layer of network proof beyond
   `network_mode=none`.
3. **eBPF telemetry** — real packet/DNS counters instead of the
   currently-hardcoded `packets_out=0` (honest right now because
   `network=none` makes it structurally true, but not yet
   *independently measured*).
4. **SecurityStatus/NetworkStatus dashboard events** streamed over
   WebSocket in real time (vs. the current audit log file).

Say the word when you want these and I'll build them the same way —
tested, contract-first, no changes required upstream.

---

## 7. Sanity checklist before you tell Member 1 "it's ready"

- [ ] `docker build` succeeds
- [ ] `pytest tests/security -v` — all 8 tests pass
- [ ] `python3 sandbox_test.py --real` shows correct status for all 4 cases
- [ ] You've read `app/security/policy.py` top to bottom and every
      limit makes sense to you (don't ship limits you can't explain)
- [ ] `MockSandboxService` and `DockerSandboxService` both pass
      `tests/contract/test_sandbox_contract.py`
