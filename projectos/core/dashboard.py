"""Dashboard — formatted status views for CEO."""
from typing import Any, Dict

from .registry import ProjectRegistry
from .scheduler import AgentScheduler
from .solo_adapter import SoloCommandError, SoloProjectAdapter


class Dashboard:
    """Generate human-readable project status reports."""

    def __init__(self, registry: ProjectRegistry, scheduler: AgentScheduler):
        self.registry = registry
        self.scheduler = scheduler

    def list_projects(self) -> str:
        """Formatted table of all projects."""
        projects = self.registry.list()
        if not projects:
            return "No projects registered."

        lines = [
            "┌──────────────────────┬──────────────────────────────┬─────────┬──────────┬─────────────────┐",
            "│ Project ID           │ Name                         │ Status  │ Kind     │ Active Tasks    │",
            "├──────────────────────┼──────────────────────────────┼─────────┼──────────┼─────────────────┤",
        ]
        for p in sorted(projects, key=lambda x: x.id):
            busy = self._active_task_count(p.id)
            status_color = self._status_color(p.status)
            lines.append(
                f"│ {p.id:<20} │ {p.name:<28} │ {status_color:<7} │ {p.kind:<8} │ {busy:>15} │"
            )
        lines.append(
            "└──────────────────────┴──────────────────────────────┴─────────┴──────────┴─────────────────┘"
        )
        return "\n".join(lines)

    def list_projects_payload(self) -> Dict[str, Any]:
        """Structured list payload for CLI/dashboard callers."""
        projects = []
        for project in self.registry.list():
            projects.append({
                "id": project.id,
                "name": project.name,
                "status": project.status,
                "kind": project.kind,
                "local_path": project.local_path,
                "repo_url": project.repo_url,
                "protocol_version": project.protocol_version,
                "health": project.health,
                "dependencies": project.dependencies,
            })
        return {
            "summary": {
                "total_projects": len(projects),
                "active_projects": len([p for p in projects if p["status"] == "active"]),
            },
            "projects": projects,
        }

    def project_status(self, project_id: str) -> str:
        payload = self.project_status_payload(project_id)
        project = payload.get("project")
        if not project:
            return f"Project '{project_id}' not found."

        lines = [
            f"📁 {project['name']} ({project_id})",
            f"   Status: {project['status']}",
            f"   Kind: {project['kind']}",
            f"   Health: {payload['health']}",
            f"   Repo: {project['repo_url']}",
            f"   Local: {project['local_path']}",
            f"   Protocol: {project['protocol_version']}",
            f"   Created: {project['created_at']}",
            "",
            "   Solo summary:",
        ]
        solo = payload.get("solo_status") or {}
        summary = solo.get("summary") or {}
        if summary:
            lines.append(f"     Tasks: {summary.get('total_tasks', 0)} total, {summary.get('active_tasks', 0)} active, {summary.get('failed_tasks', 0)} failed")
            lines.append(f"     Last updated: {summary.get('last_updated') or '-'}")
        elif payload.get("error"):
            lines.append(f"     Error: {payload['error']}")
        else:
            lines.append("     No solo status available.")

        if project["dependencies"]:
            lines.append("")
            lines.append("   Dependencies:")
            for dep in project["dependencies"]:
                lines.append(f"     → {dep}")

        return "\n".join(lines)

    def project_status_payload(self, project_id: str) -> Dict[str, Any]:
        project = self.registry.get(project_id)
        if not project:
            return {
                "ok": False,
                "project": None,
                "health": "missing",
                "error": f"Project '{project_id}' not found.",
            }
        payload: Dict[str, Any] = {
            "ok": True,
            "project": project.to_dict(),
            "health": project.health,
            "solo_status": None,
            "error": "",
        }
        if project.kind != "solo":
            payload["health"] = "legacy"
            return payload
        adapter = SoloProjectAdapter(project.local_path)
        if not adapter.is_initialized():
            payload["ok"] = False
            payload["health"] = "missing"
            payload["error"] = "No .solo/config.yaml found."
            return payload
        try:
            status = adapter.status(include_all=True)
            payload["solo_status"] = status
            protocol = status.get("protocol") or {}
            payload["health"] = "healthy" if protocol.get("compatible", True) else "migration_needed"
        except SoloCommandError as exc:
            payload["ok"] = False
            payload["health"] = "unhealthy"
            payload["error"] = exc.stderr or exc.stdout or str(exc)
        return payload

    def system_overview(self) -> str:
        """High-level system status."""
        projects = self.registry.list()
        total = len(projects)
        active = sum(1 for p in projects if p.status == "active")
        paused = sum(1 for p in projects if p.status == "paused")
        archived = sum(1 for p in projects if p.status == "archived")

        busy_agents = self.scheduler.get_busy_agents()
        idle_agents = self.scheduler.get_idle_agents()
        queued = len(self.scheduler.get_queue())

        lines = [
            "╔══════════════════════════════════════════╗",
            "║         🏢 ProjectOS Dashboard           ║",
            "╠══════════════════════════════════════════╣",
            f"║  Projects: {total:>3}  (🟢{active} 🟡{paused} ⚪{archived})      ║",
            f"║  Agents:   {len(busy_agents):>3} busy / {len(idle_agents):>3} idle        ║",
            f"║  Queue:    {queued:>3} tasks waiting             ║",
            "╚══════════════════════════════════════════╝",
        ]
        return "\n".join(lines)

    def _active_task_count(self, project_id: str) -> int:
        project = self.registry.get(project_id)
        if project and project.kind == "solo":
            try:
                status = SoloProjectAdapter(project.local_path).status(include_all=True)
            except (SoloCommandError, FileNotFoundError):
                return 0
            return int((status.get("summary") or {}).get("active_tasks") or 0)
        return sum(
            1 for a in self.scheduler.agents.values()
            if a.current_project == project_id and a.status == "busy"
        )

    def dependency_graph(self) -> str:
        """ASCII representation of project dependencies."""
        projects = self.registry.list()
        if not projects:
            return "No projects."

        lines = ["Project Dependency Graph:", ""]
        for p in sorted(projects, key=lambda x: x.id):
            deps = p.dependencies
            if deps:
                for dep in deps:
                    lines.append(f"  {dep} ──→ {p.id}")
            else:
                lines.append(f"  {p.id} (no dependencies)")
        return "\n".join(lines)

    @staticmethod
    def _status_color(status: str) -> str:
        mapping = {
            "active": "🟢 active",
            "paused": "🟡 paused",
            "archived": "⚪ archived",
        }
        return mapping.get(status, status)
