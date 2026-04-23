"""Dashboard — formatted status views for CEO."""
from typing import List, Optional
from datetime import datetime

from .models import Project, Task, AgentInstance
from .registry import ProjectRegistry
from .scheduler import AgentScheduler


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
            "┌──────────────────────┬──────────────────────────────┬─────────┬─────────────────┐",
            "│ Project ID           │ Name                         │ Status  │ Active Tasks    │",
            "├──────────────────────┼──────────────────────────────┼─────────┼─────────────────┤",
        ]
        for p in sorted(projects, key=lambda x: x.id):
            # Count in-progress tasks for this project
            busy = sum(
                1 for a in self.scheduler.agents.values()
                if a.current_project == p.id and a.status == "busy"
            )
            status_color = self._status_color(p.status)
            lines.append(
                f"│ {p.id:<20} │ {p.name:<28} │ {status_color:<7} │ {busy:>15} │"
            )
        lines.append(
            "└──────────────────────┴──────────────────────────────┴─────────┴─────────────────┘"
        )
        return "\n".join(lines)

    def project_status(self, project_id: str) -> str:
        project = self.registry.get(project_id)
        if not project:
            return f"Project '{project_id}' not found."

        lines = [
            f"📁 {project.name} ({project_id})",
            f"   Status: {project.status}",
            f"   Repo: {project.repo_url}",
            f"   Local: {project.local_path}",
            f"   Created: {project.created_at}",
            "",
            "   Team:",
        ]
        for role, enabled in project.team.items():
            status = "✅" if enabled else "❌"
            lines.append(f"     {status} {role}")

        if project.dependencies:
            lines.append("")
            lines.append("   Dependencies:")
            for dep in project.dependencies:
                lines.append(f"     → {dep}")

        lines.append("")
        lines.append("   Active Agents:")
        active = [
            a for a in self.scheduler.agents.values()
            if a.current_project == project_id and a.status == "busy"
        ]
        if active:
            for a in active:
                lines.append(f"     🤖 {a.id} → {a.current_task}")
        else:
            lines.append("     (none)")

        return "\n".join(lines)

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
