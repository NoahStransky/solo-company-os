"""ProjectOS CLI — multi-project command center."""
import argparse
import json
import sys
from pathlib import Path

# Ensure projectos is importable
sys.path.insert(0, str(Path(__file__).parent.parent))

from projectos.core import ProjectRegistry, AgentScheduler, StateManager
from projectos.core import DependencyManager, Dashboard
from projectos.core.models import Project
from projectos.core.orchestrator import CrossProjectOrchestrator, parse_dependency_specs
from projectos.core.solo_adapter import SoloCommandError, SoloProjectAdapter


def cmd_list(args):
    registry = ProjectRegistry()
    scheduler = AgentScheduler(registry)
    dashboard = Dashboard(registry, scheduler)
    if args.json:
        print(json.dumps(dashboard.list_projects_payload(), indent=2, ensure_ascii=False))
        return
    print(dashboard.system_overview())
    print()
    print(dashboard.list_projects())


def cmd_status(args):
    registry = ProjectRegistry()
    scheduler = AgentScheduler(registry)
    dashboard = Dashboard(registry, scheduler)
    if not args.project_id:
        orchestrator = CrossProjectOrchestrator(registry)
        payload = {
            "projects": dashboard.list_projects_payload(),
            "cross_tasks": orchestrator.status_payload(),
        }
        if args.json:
            print(json.dumps(payload, indent=2, ensure_ascii=False))
            return
        print(dashboard.system_overview())
        print()
        print(_format_cross_tasks(payload["cross_tasks"]))
        return
    if args.json:
        print(json.dumps(dashboard.project_status_payload(args.project_id), indent=2, ensure_ascii=False))
        return
    print(dashboard.project_status(args.project_id))


def cmd_inspect(args):
    registry = ProjectRegistry()
    project = registry.get(args.project_id)
    if not project:
        print(f"Project '{args.project_id}' not found.", file=sys.stderr)
        sys.exit(1)
    try:
        payload = SoloProjectAdapter(project.local_path).inspect(task_id=args.task or "")
    except SoloCommandError as exc:
        print(exc.stderr or exc.stdout or str(exc), file=sys.stderr)
        sys.exit(exc.returncode or 1)
    print(json.dumps(payload, indent=2, ensure_ascii=False))


def cmd_validate(args):
    registry = ProjectRegistry()
    project = registry.get(args.project_id)
    if not project:
        print(f"Project '{args.project_id}' not found.", file=sys.stderr)
        sys.exit(1)
    payload = SoloProjectAdapter(project.local_path).validate()
    if args.json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        if payload.get("ok", False):
            print(f"✅ {args.project_id} healthy")
        else:
            print(f"❌ {args.project_id} unhealthy")
            for issue in payload.get("errors", []):
                print(f"ERROR {issue.get('code')}: {issue.get('message')}")
            for issue in payload.get("warnings", []):
                print(f"WARN {issue.get('code')}: {issue.get('message')}")
    if not payload.get("ok", False):
        sys.exit(1)


def cmd_dispatch(args):
    registry = ProjectRegistry()
    if not args.items:
        print("dispatch requires a task.", file=sys.stderr)
        sys.exit(1)

    project = registry.get(args.items[0])
    if project and not args.project:
        if len(args.items) < 2:
            print("project dispatch requires a task.", file=sys.stderr)
            sys.exit(1)
        try:
            payload = SoloProjectAdapter(project.local_path).dispatch(
                task=" ".join(args.items[1:]).strip(),
                role=args.to or "",
                workflow=args.workflow or "",
            )
        except SoloCommandError as exc:
            print(exc.stderr or exc.stdout or str(exc), file=sys.stderr)
            sys.exit(exc.returncode or 1)
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return

    try:
        dependencies = parse_dependency_specs(list(args.depends))
        task = CrossProjectOrchestrator(registry).dispatch(
            title=" ".join(args.items).strip(),
            project_ids=list(args.project),
            dependencies=dependencies,
            workflow=args.workflow or "",
        )
    except (KeyError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(1)
    payload = {"ok": True, "cross_task": task.to_dict()}
    if args.json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        print(_format_cross_task(task.to_dict()))


def cmd_run(args):
    registry = ProjectRegistry()
    try:
        task = CrossProjectOrchestrator(registry).run(task_id=args.task or "", until=args.until)
    except (KeyError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(1)
    payload = {"ok": task.status != "failed", "cross_task": task.to_dict()}
    if args.json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return
    print(_format_cross_task(task.to_dict()))
    if task.status == "failed":
        sys.exit(1)


def cmd_retry(args):
    registry = ProjectRegistry()
    try:
        task = CrossProjectOrchestrator(registry).retry(
            project_id=args.project_id,
            task_id=args.task or "",
            phase=args.phase or "",
            agent=args.agent or "",
        )
    except SoloCommandError as exc:
        print(exc.stderr or exc.stdout or str(exc), file=sys.stderr)
        sys.exit(exc.returncode or 1)
    except (KeyError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(1)
    payload = {"ok": True, "cross_task": task.to_dict()}
    if args.json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        print(_format_cross_task(task.to_dict()))


def cmd_reopen(args):
    registry = ProjectRegistry()
    try:
        task = CrossProjectOrchestrator(registry).reopen(
            project_id=args.project_id,
            phase=args.phase,
            task_id=args.task or "",
        )
    except SoloCommandError as exc:
        print(exc.stderr or exc.stdout or str(exc), file=sys.stderr)
        sys.exit(exc.returncode or 1)
    except (KeyError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(1)
    payload = {"ok": True, "cross_task": task.to_dict()}
    if args.json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        print(_format_cross_task(task.to_dict()))


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


def cmd_project_add(args):
    registry = ProjectRegistry()
    try:
        pid = registry.add_solo_project(args.path, project_id=args.id, name=args.name)
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(1)
    print(f"✅ Registered solo project '{pid}'")


def cmd_project_scan(args):
    root = Path(args.root).expanduser().resolve()
    registry = ProjectRegistry()
    added = []
    for config_path in sorted(root.rglob(".solo/config.yaml")):
        project_path = config_path.parent.parent
        try:
            pid = registry.add_solo_project(str(project_path))
        except ValueError:
            continue
        added.append(pid)
    if args.json:
        print(json.dumps({"root": str(root), "added": added}, indent=2, ensure_ascii=False))
        return
    print(f"Scanned {root}")
    print(f"Added: {', '.join(added) if added else '-'}")


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


def _format_cross_tasks(payload):
    tasks = payload.get("cross_tasks", [])
    if not tasks:
        return "No cross-project tasks."
    lines = ["Cross-project tasks:"]
    for task in tasks:
        lines.append(f"  {task['id']} [{task['status']}] {task['title']}")
        for node in task.get("project_tasks", []):
            deps = f" depends_on={','.join(node.get('depends_on', []))}" if node.get("depends_on") else ""
            solo_id = f" solo={node.get('solo_task_id')}" if node.get("solo_task_id") else ""
            lines.append(f"    - {node['project_id']}: {node['status']}{solo_id}{deps}")
    return "\n".join(lines)


def _format_cross_task(task):
    return _format_cross_tasks({"cross_tasks": [task]})


def main():
    parser = argparse.ArgumentParser(
        prog="projectos",
        description="ProjectOS — Multi-project AI Agent Command Center",
    )
    subparsers = parser.add_subparsers(dest="command")

    # list
    p_list = subparsers.add_parser("list", help="Show all projects")
    p_list.add_argument("--json", action="store_true", help="Print structured JSON")

    # status
    p_status = subparsers.add_parser("status", help="Show project details")
    p_status.add_argument("project_id", nargs="?")
    p_status.add_argument("--json", action="store_true", help="Print structured JSON")

    # inspect
    p_inspect = subparsers.add_parser("inspect", help="Proxy solo inspect for a project")
    p_inspect.add_argument("project_id")
    p_inspect.add_argument("--task", default="", help="Task id")

    # validate
    p_validate = subparsers.add_parser("validate", help="Proxy solo validate for a project")
    p_validate.add_argument("project_id")
    p_validate.add_argument("--json", action="store_true", help="Print structured JSON")

    # dispatch
    p_dispatch = subparsers.add_parser("dispatch", help="Dispatch a project task or cross-project task")
    p_dispatch.add_argument("items", nargs="+", help="Either '<project_id> <task...>' or a cross-project task title")
    p_dispatch.add_argument("--to", default="", help="Agent role")
    p_dispatch.add_argument("--workflow", default="", help="Workflow name")
    p_dispatch.add_argument("--project", action="append", default=[], help="Project id for cross-project dispatch. Repeat for multiple projects.")
    p_dispatch.add_argument("--depends", action="append", default=[], help="Cross-project dependency as project:dependency[,dependency].")
    p_dispatch.add_argument("--json", action="store_true", help="Print structured JSON")

    # run
    p_run = subparsers.add_parser("run", help="Run the latest or selected cross-project task")
    p_run.add_argument("--task", default="", help="Cross-project task id. Defaults to latest.")
    p_run.add_argument("--until", default="done", help="Run child solo tasks until this target.")
    p_run.add_argument("--json", action="store_true", help="Print structured JSON")

    # retry
    p_retry = subparsers.add_parser("retry", help="Retry one project node through child solo retry")
    p_retry.add_argument("project_id", help="Project node id")
    p_retry.add_argument("--task", default="", help="Cross-project task id. Defaults to latest.")
    p_retry.add_argument("--phase", default="", help="Child solo phase to retry")
    p_retry.add_argument("--agent", default="", help="Child solo agent instance to retry")
    p_retry.add_argument("--json", action="store_true", help="Print structured JSON")

    # reopen
    p_reopen = subparsers.add_parser("reopen", help="Reopen one project node through child solo reopen")
    p_reopen.add_argument("project_id", help="Project node id")
    p_reopen.add_argument("--task", default="", help="Cross-project task id. Defaults to latest.")
    p_reopen.add_argument("--phase", required=True, help="Child solo phase to reopen")
    p_reopen.add_argument("--json", action="store_true", help="Print structured JSON")

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

    # project
    p_project = subparsers.add_parser("project", help="Manage registered solo projects")
    project_subparsers = p_project.add_subparsers(dest="project_command")
    p_project_add = project_subparsers.add_parser("add", help="Register an initialized solo project")
    p_project_add.add_argument("path")
    p_project_add.add_argument("--id", default=None, help="Registry id")
    p_project_add.add_argument("--name", default=None, help="Display name")
    p_project_scan = project_subparsers.add_parser("scan", help="Scan a directory for .solo projects")
    p_project_scan.add_argument("root")
    p_project_scan.add_argument("--json", action="store_true", help="Print structured JSON")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    commands = {
        "list": cmd_list,
        "status": cmd_status,
        "inspect": cmd_inspect,
        "validate": cmd_validate,
        "dispatch": cmd_dispatch,
        "run": cmd_run,
        "retry": cmd_retry,
        "reopen": cmd_reopen,
        "create": cmd_create,
        "pause": cmd_pause,
        "resume": cmd_resume,
        "deps": cmd_deps,
    }

    if args.command == "project":
        if args.project_command == "add":
            cmd_project_add(args)
        elif args.project_command == "scan":
            cmd_project_scan(args)
        else:
            p_project.print_help()
            sys.exit(1)
    else:
        func = commands.get(args.command)
        if not func:
            parser.print_help()
            return
        func(args)


if __name__ == "__main__":
    main()
