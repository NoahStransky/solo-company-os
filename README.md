# ProjectOS / solo-os — Multi-Project Solo Control Plane

ProjectOS is the control plane for multiple initialized `solo` projects. It does not replace the single-project `solo` runtime; it registers projects, reads their `.solo/` protocol, calls public `solo ... --json` commands, and renders a global dashboard.

## Problem

You have N initialized `solo` projects. Each project owns its own workflow, task state, messages, artifacts, retry state, and runtime config.

How do you see and coordinate them without opening every repository?

## Solution

ProjectOS provides:

- **Project Registry** — Register existing projects that contain `.solo/config.yaml`
- **Solo Adapter** — Call `solo status --json`, `solo inspect --json`, `solo validate --json`, and `solo dispatch --json`
- **Cross-Project Tasks** — Create one CEO-level task graph and dispatch project nodes into child `solo` runtimes
- **Dashboard CLI** — Show health and task summaries across projects
- **Dependency Manager** — Track cross-project dependencies
- **Read-only First** — Prefer status/inspect/validate before mutating child projects

## Architecture

```text
CEO (Human)
  ↓
solo-os CLI / Dashboard
  ↓
┌─────────────────────────────────────────┐
│             ProjectOS Core              │
│ Registry → Solo Adapter → Dashboard     │
└─────────────────────────────────────────┘
  ↓                    ↓                  ↓
Project A            Project B          Project C
.solo/ protocol      .solo/ protocol    .solo/ protocol
```

## Quick Start

```bash
# Install
pip install -e .

# Register an initialized solo project
solo-os project add ../my-solo-project --id my-solo-project

# See all registered projects
solo-os list --json

# Check project status through solo status --json
solo-os status my-solo-project --json

# Inspect a task through solo inspect --json
solo-os inspect my-solo-project --task TASK-...

# Validate child project protocol
solo-os validate my-solo-project --json

# Dispatch into a child solo project
solo-os dispatch my-solo-project "Build RSS import"

# Or dispatch one CEO-level cross-project task into selected projects
solo-os dispatch "Build billing feature" \
  --project backend \
  --project frontend \
  --depends frontend:backend \
  --json

# Run the latest cross-project task until every ready child solo task is done
solo-os run --until done --json

# Recover a failed or reopened project node through the child solo project
solo-os retry backend --task XPROJ-20260528-001 --phase dev_pool --json
solo-os reopen frontend --task XPROJ-20260528-001 --phase qa --json

# See global project and cross-task status
solo-os status --json
```

If `solo` is not installed on `PATH`, point ProjectOS at it:

```bash
export PYTHONPATH="../solo-company-architecture/src:$PYTHONPATH"
export SOLO_OS_SOLO_COMMAND="python -m solo"
```

## Project Structure

```text
solo-company-os/
├── projectos/
│   ├── core/               # Registry, Solo Adapter, Deps, Dashboard
│   ├── agents/prompts/     # Legacy prompt assets
│   └── __main__.py         # CLI entry point
├── projects/               # Example project records
├── tests/                  # pytest suite
└── docs/                   # Research and design docs
```

## Boundary

ProjectOS should not import `solo.core.*` from child projects and should not write `.solo/state/*` directly. The child project remains the source of truth. ProjectOS talks to it through:

- `.solo/config.yaml`
- `solo status --json --all`
- `solo inspect --json`
- `solo validate --json`
- `solo migrate --check --json`
- `solo dispatch --json`
- `solo run --until done --json`

## Cross-Project MVP

The first cross-project loop is intentionally small:

```text
CEO request
  -> ProjectOS cross task
  -> project-level task graph
  -> child solo dispatch/run per ready project
  -> dependency unblock
  -> ProjectOS final report
```

State is stored in `projectos/state/cross_tasks.json`; events are appended to `projectos/state/events.jsonl`. A project node can be `pending`, `blocked`, `in_progress`, `completed`, or `failed`. Dependencies are declared with `--depends consumer:provider`, so `frontend:backend` means the frontend node waits until backend completes.

Current scope:

- Dispatches project nodes through public `solo dispatch --json`
- Runs project nodes through public `solo run --until done --json`
- Injects completed dependency context from public `solo inspect --json` before dispatching downstream project nodes
- Bridges recovery through public `solo retry --json` and `solo reopen --json`
- Keeps child project `.solo/` state authoritative
- Aggregates cross-task status in `solo-os status --json`

Current verification:

```bash
docker run --rm -v "$PWD:/app" -w /app solo-company:dev \
  sh -c "pip install -e . >/tmp/projectos-pip.log && pytest tests/ -q"
# 35 passed
```

## Development

```bash
# Run tests
pytest tests/ -v

# Run the solo integration tests
pytest tests/test_solo_adapter.py -v
```

## License

MIT
