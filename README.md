# ProjectOS / solo-os — Multi-Project Solo Control Plane

ProjectOS is the control plane for multiple initialized `solo` projects. It does not replace the single-project `solo` runtime; it registers projects, reads their `.solo/` protocol, calls public `solo ... --json` commands, and renders a global dashboard.

## Problem

You have N initialized `solo` projects. Each project owns its own workflow, task state, messages, artifacts, retry state, and runtime config.

How do you see and coordinate them without opening every repository?

## Solution

ProjectOS provides:

- **Project Registry** — Register existing projects that contain `.solo/config.yaml`
- **Solo Adapter** — Call `solo status --json`, `solo inspect --json`, `solo validate --json`, and `solo dispatch --json`
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

## Development

```bash
# Run tests
pytest tests/ -v

# Run the solo integration tests
pytest tests/test_solo_adapter.py -v
```

## License

MIT
