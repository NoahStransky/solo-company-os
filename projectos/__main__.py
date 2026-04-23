"""ProjectOS CLI — multi-project command center."""
import argparse
import sys
from pathlib import Path

# Ensure projectos is importable
sys.path.insert(0, str(Path(__file__).parent.parent))

from projectos.core import ProjectRegistry, AgentScheduler, StateManager
from projectos.core import DependencyManager, Dashboard
from projectos.core.models import Project


def cmd_list(args):
    registry = ProjectRegistry()
    scheduler = AgentScheduler(registry)
    dashboard = Dashboard(registry, scheduler)
    print(dashboard.system_overview())
    print()
    print(dashboard.list_projects())


def cmd_status(args):
    registry = ProjectRegistry()
    scheduler = AgentScheduler(registry)
    dashboard = Dashboard(registry, scheduler)
    print(dashboard.project_status(args.project_id))


def cmd_create(args):
    registry = ProjectRegistry()
    project = Project(
        id=args.name.lower().replace(" ", "-"),
        name=args.name,
        repo_url=args.repo or "",
        local_path=args.local or f"projects/{args.name.lower().replace(' ', '-')}",
    )
    pid = registry.create(project)
    print(f"✅ Created project '{pid}' at {project.local_path}")


def cmd_pause(args):
    registry = ProjectRegistry()
    registry.update(args.project_id, status="paused")
    print(f"⏸️  Project '{args.project_id}' paused.")


def cmd_resume(args):
    registry = ProjectRegistry()
    registry.update(args.project_id, status="active")
    print(f"▶️  Project '{args.project_id}' resumed.")


def cmd_deps(args):
    registry = ProjectRegistry()
    dm = DependencyManager(registry)
    if args.visualize:
        dashboard = Dashboard(registry, AgentScheduler(registry))
        print(dashboard.dependency_graph())
    else:
        order = dm.build_order()
        print("Build order:")
        for i, pid in enumerate(order, 1):
            print(f"  {i}. {pid}")


def main():
    parser = argparse.ArgumentParser(
        prog="projectos",
        description="ProjectOS — Multi-project AI Agent Command Center",
    )
    subparsers = parser.add_subparsers(dest="command")

    # list
    subparsers.add_parser("list", help="Show all projects")

    # status
    p_status = subparsers.add_parser("status", help="Show project details")
    p_status.add_argument("project_id")

    # create
    p_create = subparsers.add_parser("create", help="Register a new project")
    p_create.add_argument("name")
    p_create.add_argument("--repo", default="")
    p_create.add_argument("--local", default="")

    # pause
    p_pause = subparsers.add_parser("pause", help="Pause a project")
    p_pause.add_argument("project_id")

    # resume
    p_resume = subparsers.add_parser("resume", help="Resume a project")
    p_resume.add_argument("project_id")

    # deps
    p_deps = subparsers.add_parser("deps", help="Dependency management")
    p_deps.add_argument("--visualize", action="store_true", help="Show dependency graph")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    commands = {
        "list": cmd_list,
        "status": cmd_status,
        "create": cmd_create,
        "pause": cmd_pause,
        "resume": cmd_resume,
        "deps": cmd_deps,
    }

    func = commands.get(args.command)
    if func:
        func(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
