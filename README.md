# 🏢 ProjectOS — Multi-Project AI Agent Command Center

ProjectOS is the orchestration layer for running **multiple Solo Company AI Agent teams** in parallel.

## Problem

You have N projects. Each project needs its own team of AI Agents (CTO, Dev, QA, Growth...).
How do you manage them all without chaos?

## Solution

ProjectOS provides:

- **Project Registry** — Track all projects with their repos, teams, and status
- **Agent Scheduler** — Allocate AI Agents across projects without conflicts
- **State Manager** — Persist task states, recover from crashes
- **Dependency Manager** — Handle cross-project dependencies (e.g., API → Frontend)
- **Dashboard CLI** — One command to see everything: `python -m projectos list`

## Architecture

```
CEO (Human)
  ↓
Secretary Agent
  ↓
┌─────────────────────────────────────────┐
│           ProjectOS Core                │
│  Registry → Scheduler → State → Deps   │
└─────────────────────────────────────────┘
  ↓                    ↓                  ↓
Project A (Hotspot)  Project B (API)   Project C (Landing)
  Solo Company         Solo Company      Solo Company
```

## Quick Start

```bash
# Install
pip install -e .

# See all projects
python -m projectos list

# Register a new project
python -m projectos create "My Project" --repo https://github.com/user/repo

# Check project status
python -m projectos status my-project

# View dependency graph
python -m projectos deps --visualize
```

## Example Projects

Two example projects are included:

| Project | Description | Dependencies |
|---------|-------------|--------------|
| `project-a-hotspot` | AI tech news aggregator | None |
| `project-b-api` | FastAPI service for hotspot data | `project-a-hotspot` |

## Project Structure

```
solo-company-os/
├── projectos/              # Core framework
│   ├── core/               # Registry, Scheduler, State, Deps, Dashboard
│   ├── agents/prompts/     # Agent system prompts (CTO, Dev, QA...)
│   └── __main__.py         # CLI entry point
├── projects/               # Project sandboxes
│   ├── project-a-hotspot/
│   └── project-b-api/
├── tests/                  # pytest suite
└── docs/architecture/      # Design docs
```

## Agent Prompts

Each Agent role has a system prompt template in `projectos/agents/prompts/`:

- **secretary.md** — Coordination and dispatch
- **cto.md** — Architecture design and code review
- **dev.md** — TDD-driven implementation
- **qa.md** — Independent testing and validation
- **growth.md** — Marketing and distribution

## Development

```bash
# Run tests
pytest tests/ -v

# Run a specific module test
pytest tests/test_scheduler.py -v
```

## License

MIT
